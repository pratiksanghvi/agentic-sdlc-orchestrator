package com.example.shortener.service;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class UrlValidatorTest {

    private final UrlValidator validator = new UrlValidator();

    @ParameterizedTest
    @ValueSource(strings = {"http://example.com", "https://example.com/a/b?x=1", "HTTPS://Example.com", "http://localhost:8080/x"})
    void acceptsValid(String url) {
        assertDoesNotThrow(() -> validator.validate(url));
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   ", "/relative/path", "example.com", "ftp://example.com", "javascript:alert(1)", "http://", "http:///path", "http://exa mple.com", "mailto:a@b.com"})
    void rejectsInvalid(String url) {
        assertThrows(InvalidUrlException.class, () -> validator.validate(url));
    }

    @Test
    void rejectsNull() {
        assertThrows(InvalidUrlException.class, () -> validator.validate(null));
    }
}
