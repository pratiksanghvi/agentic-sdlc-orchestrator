package com.example.shortener.api;

public record ShortLinkResponse(String shortCode, String longUrl, String createdAt) {
}
