package com.example.shortener.persistence;

import java.time.Instant;

public record ShortLinkRecord(String shortCode, String longUrl, Instant createdAt, long clickCount, Instant lastClickedAt) {
}
