package com.example.shortener.persistence;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class ShortLinkRepositoryTest {

    private static final Path DB;

    static {
        try {
            DB = Files.createTempFile("shortener-repo-test", ".db");
            DB.toFile().deleteOnExit();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:sqlite:" + DB.toAbsolutePath());
    }

    @Autowired
    ShortLinkRepository repo;

    @Autowired
    JdbcTemplate jdbc;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM short_links");
    }

    @Test
    void insertAndFind() {
        Instant t = Instant.now().truncatedTo(ChronoUnit.MICROS);
        repo.insert("abc1234", "https://example.com/x", t);
        ShortLinkRecord r = repo.findByCode("abc1234").orElseThrow();
        assertEquals("https://example.com/x", r.longUrl());
        assertEquals(t, r.createdAt());
        assertEquals(0, r.clickCount());
        assertNull(r.lastClickedAt());
    }

    @Test
    void duplicateCodeSurfaces() {
        repo.insert("dup1234", "https://a.example", Instant.now());
        assertThrows(DuplicateKeyException.class,
                () -> repo.insert("dup1234", "https://b.example", Instant.now()));
    }

    @Test
    void unknownCodeEmpty() {
        assertTrue(repo.findByCode("nope").isEmpty());
        assertTrue(repo.findLongUrl("nope").isEmpty());
        assertEquals(0, repo.incrementClick("nope", Instant.now()));
    }

    @Test
    void incrementClickCounts() {
        repo.insert("clk1234", "https://example.com", Instant.now());
        Instant now = Instant.now().truncatedTo(ChronoUnit.MICROS);
        assertEquals(1, repo.incrementClick("clk1234", now));
        assertEquals(1, repo.incrementClick("clk1234", now));
        ShortLinkRecord r = repo.findByCode("clk1234").orElseThrow();
        assertEquals(2, r.clickCount());
        assertEquals(now, r.lastClickedAt());
        assertEquals("https://example.com", repo.findLongUrl("clk1234").orElseThrow());
    }
}
