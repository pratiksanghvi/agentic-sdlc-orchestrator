package com.example.shortener;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@SpringBootTest
class ShortenerApplicationTests {

    private static final Path DB;

    static {
        try {
            DB = Files.createTempFile("shortener-test", ".db");
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
    JdbcTemplate jdbc;

    @Test
    void contextLoadsAndSchemaApplied() {
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM short_links", Integer.class);
        assertEquals(0, n);
    }
}
