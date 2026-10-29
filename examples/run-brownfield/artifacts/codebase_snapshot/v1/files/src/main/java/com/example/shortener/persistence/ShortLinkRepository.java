package com.example.shortener.persistence;

import java.sql.SQLException;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Optional;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.UncategorizedSQLException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

@Repository
public class ShortLinkRepository {

    private static final int SQLITE_CONSTRAINT = 19;

    private static final DateTimeFormatter FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'").withZone(ZoneOffset.UTC);

    private static final RowMapper<ShortLinkRecord> MAPPER = (rs, i) -> {
        String last = rs.getString("last_clicked_at");
        return new ShortLinkRecord(
                rs.getString("short_code"),
                rs.getString("long_url"),
                Instant.parse(rs.getString("created_at")),
                rs.getLong("click_count"),
                last == null ? null : Instant.parse(last));
    };

    private final JdbcTemplate jdbc;

    public ShortLinkRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    static String format(Instant instant) {
        return FORMAT.format(instant.truncatedTo(ChronoUnit.MICROS));
    }

    /** Inserts a new row; throws DuplicateKeyException on short_code collision. */
    public void insert(String shortCode, String longUrl, Instant createdAt) {
        try {
            jdbc.update(
                    "INSERT INTO short_links (short_code, long_url, created_at, click_count, last_clicked_at) VALUES (?, ?, ?, 0, NULL)",
                    shortCode, longUrl, format(createdAt));
        } catch (UncategorizedSQLException e) {
            SQLException cause = e.getSQLException();
            if (cause != null && cause.getErrorCode() == SQLITE_CONSTRAINT
                    && String.valueOf(cause.getMessage()).contains("UNIQUE")) {
                throw new DuplicateKeyException("duplicate short_code", e);
            }
            throw e;
        }
    }

    public Optional<ShortLinkRecord> findByCode(String shortCode) {
        List<ShortLinkRecord> rows = jdbc.query(
                "SELECT short_code, long_url, created_at, click_count, last_clicked_at FROM short_links WHERE short_code = ?",
                MAPPER, shortCode);
        return rows.stream().findFirst();
    }

    public int incrementClick(String shortCode, Instant now) {
        return jdbc.update(
                "UPDATE short_links SET click_count = click_count + 1, last_clicked_at = ? WHERE short_code = ?",
                format(now), shortCode);
    }

    public Optional<String> findLongUrl(String shortCode) {
        List<String> rows = jdbc.queryForList(
                "SELECT long_url FROM short_links WHERE short_code = ?", String.class, shortCode);
        return rows.stream().findFirst();
    }
}
