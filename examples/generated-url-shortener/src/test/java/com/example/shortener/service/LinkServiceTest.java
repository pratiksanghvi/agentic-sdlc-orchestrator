package com.example.shortener.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.example.shortener.persistence.ShortLinkRecord;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class LinkServiceTest {

    private static final Path DB;

    static {
        try {
            DB = Files.createTempFile("shortener-service-test", ".db");
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
    LinkService service;

    @Autowired
    JdbcTemplate jdbc;

    @BeforeEach
    void clean() {
        jdbc.update("DELETE FROM short_links");
    }

    @Test
    void createsIndependentLinks() {
        ShortLinkRecord a = service.create("https://example.com/a");
        ShortLinkRecord b = service.create("https://example.com/a");
        assertNotEquals(a.shortCode(), b.shortCode());
        assertEquals("https://example.com/a", a.longUrl());
        assertNotNull(a.createdAt());
        assertEquals(0, a.clickCount());
    }

    @Test
    void invalidUrlPersistsNothing() {
        assertThrows(InvalidUrlException.class, () -> service.create("ftp://x.com"));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM short_links", Integer.class));
    }

    @Test
    void resolveCountsClicks() {
        ShortLinkRecord l = service.create("https://example.com/z");
        assertNull(service.getAnalytics(l.shortCode()).lastClickedAt());
        assertEquals("https://example.com/z", service.resolveAndCount(l.shortCode()));
        service.resolveAndCount(l.shortCode());
        ShortLinkRecord r = service.getAnalytics(l.shortCode());
        assertEquals(2, r.clickCount());
        assertNotNull(r.lastClickedAt());
    }

    @Test
    void unknownCodeThrows() {
        assertThrows(LinkNotFoundException.class, () -> service.resolveAndCount("nope"));
        assertThrows(LinkNotFoundException.class, () -> service.getDetails("nope"));
        assertThrows(LinkNotFoundException.class, () -> service.getAnalytics("nope"));
        assertEquals(0, jdbc.queryForObject("SELECT COUNT(*) FROM short_links", Integer.class));
    }
}
