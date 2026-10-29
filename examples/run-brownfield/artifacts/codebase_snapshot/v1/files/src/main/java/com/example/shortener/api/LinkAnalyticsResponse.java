package com.example.shortener.api;

public record LinkAnalyticsResponse(String shortCode, long clickCount, String lastClickedAt) {
}
