// Transactional outbox relay. Delivery is at least once; consumers deduplicate by event ID.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"github.com/segmentio/kafka-go"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync/atomic"
	"syscall"
	"time"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	pool, err := pgxpool.New(ctx, os.Getenv("RELAY_DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	defer pool.Close()
	writer := &kafka.Writer{Addr: kafka.TCP(strings.Split(os.Getenv("KAFKA_BROKERS"), ",")...), Topic: "assemblylens.events", Balancer: &kafka.Hash{}, RequiredAcks: kafka.RequireAll, WriteTimeout: 10 * time.Second}
	defer writer.Close()
	cache := redis.NewClient(&redis.Options{Addr: os.Getenv("REDIS_ADDR")})
	defer cache.Close()
	client := &http.Client{Timeout: 10 * time.Second}
	var sent atomic.Int64
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if pool.Ping(r.Context()) != nil {
			http.Error(w, "database unavailable", 503)
			return
		}
		fmt.Fprint(w, "ok")
	})
	mux.HandleFunc("/metrics", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "assemblylens_relay_delivered_total %d\n", sent.Load())
	})
	server := &http.Server{Addr: ":9091", Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Print(err)
		}
	}()
	defer server.Close()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			batchCtx, done := context.WithTimeout(ctx, 30*time.Second)
			err = deliver(batchCtx, pool, writer, cache, client, &sent)
			done()
			if err != nil {
				log.Printf("outbox retry: %v", err)
			}
		}
	}
}

func deliver(ctx context.Context, pool *pgxpool.Pool, writer *kafka.Writer, cache *redis.Client, client *http.Client, sent *atomic.Int64) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	rows, err := tx.Query(ctx, "SELECT id, body FROM outbox WHERE delivered IS NULL ORDER BY created LIMIT 20 FOR UPDATE SKIP LOCKED")
	if err != nil {
		return err
	}
	type item struct {
		id   string
		body []byte
	}
	var items []item
	for rows.Next() {
		var it item
		if err = rows.Scan(&it.id, &it.body); err != nil {
			rows.Close()
			return err
		}
		items = append(items, it)
	}
	rows.Close()
	if rows.Err() != nil {
		return rows.Err()
	}
	for _, it := range items {
		var e map[string]interface{}
		if err = json.Unmarshal(it.body, &e); err != nil {
			return err
		}
		if err = writer.WriteMessages(ctx, kafka.Message{Key: []byte(it.id), Value: it.body}); err != nil {
			return err
		}
		// ClickHouse stores the authoritative event ID and the tenant for scoped analysis.
		row, _ := json.Marshal(map[string]interface{}{"id": it.id, "tenant": e["tenant"], "action": e["action"], "payload": string(it.body)})
		req, err := http.NewRequestWithContext(ctx, "POST", os.Getenv("CLICKHOUSE_URL")+"/?query=INSERT%20INTO%20assemblylens.events%20FORMAT%20JSONEachRow", bytes.NewReader(row))
		if err != nil {
			return err
		}
		req.SetBasicAuth(os.Getenv("CLICKHOUSE_USER"), os.Getenv("CLICKHOUSE_PASSWORD"))
		response, err := client.Do(req)
		if err != nil {
			return err
		}
		response.Body.Close()
		if response.StatusCode != 200 {
			return fmt.Errorf("analytics write HTTP %d", response.StatusCode)
		}
		// Redis notifications are hints. Durable delivery is Kafka and PostgreSQL, not pub/sub.
		if err = cache.Publish(ctx, "assemblylens:"+fmt.Sprint(e["tenant"]), string(it.body)).Err(); err != nil {
			return err
		}
		if _, err = tx.Exec(ctx, "UPDATE outbox SET delivered=now() WHERE id=$1", it.id); err != nil {
			return err
		}
	}
	if err = tx.Commit(ctx); err != nil {
		return err
	}
	sent.Add(int64(len(items)))
	return nil
}
