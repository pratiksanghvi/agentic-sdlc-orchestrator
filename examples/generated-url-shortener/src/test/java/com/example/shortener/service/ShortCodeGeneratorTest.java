package com.example.shortener.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.Set;
import org.junit.jupiter.api.Test;

class ShortCodeGeneratorTest {

    private final ShortCodeGenerator generator = new ShortCodeGenerator();

    @Test
    void generatesSevenBase62Chars() {
        for (int i = 0; i < 200; i++) {
            String code = generator.generate();
            assertEquals(7, code.length());
            assertTrue(code.matches("[A-Za-z0-9]{7}"));
        }
    }

    @Test
    void codesVary() {
        Set<String> codes = new HashSet<>();
        for (int i = 0; i < 100; i++) {
            codes.add(generator.generate());
        }
        assertTrue(codes.size() > 90);
    }
}
