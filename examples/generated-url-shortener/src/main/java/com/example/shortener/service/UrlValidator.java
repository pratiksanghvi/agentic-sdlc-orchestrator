package com.example.shortener.service;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import org.springframework.stereotype.Component;

@Component
public class UrlValidator {

    private static final String MESSAGE = "url must be an absolute http or https URL";

    public void validate(String url) {
        if (url == null || url.isBlank()) {
            throw new InvalidUrlException(MESSAGE);
        }
        URI uri;
        try {
            uri = new URI(url);
        } catch (URISyntaxException e) {
            throw new InvalidUrlException(MESSAGE);
        }
        if (!uri.isAbsolute()) {
            throw new InvalidUrlException(MESSAGE);
        }
        String scheme = uri.getScheme().toLowerCase(Locale.ROOT);
        if (!scheme.equals("http") && !scheme.equals("https")) {
            throw new InvalidUrlException(MESSAGE);
        }
        String host = uri.getHost();
        if (host == null || host.isEmpty()) {
            throw new InvalidUrlException(MESSAGE);
        }
    }
}
