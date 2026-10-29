package com.example.shortener.service;

import com.example.shortener.persistence.ShortLinkRecord;
import com.example.shortener.persistence.ShortLinkRepository;
import java.time.Instant;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class LinkService {

    static final int MAX_ATTEMPTS = 5;

    private final ShortLinkRepository repository;
    private final UrlValidator validator;
    private final ShortCodeGenerator generator;

    public LinkService(ShortLinkRepository repository, UrlValidator validator, ShortCodeGenerator generator) {
        this.repository = repository;
        this.validator = validator;
        this.generator = generator;
    }

    public ShortLinkRecord create(String url) {
        validator.validate(url);
        Instant createdAt = Instant.now();
        for (int attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
            String code = generator.generate();
            try {
                repository.insert(code, url, createdAt);
            } catch (DuplicateKeyException e) {
                continue;
            }
            return repository.findByCode(code).orElseThrow(() -> new IllegalStateException("inserted link not found"));
        }
        throw new IllegalStateException("could not generate a unique short code");
    }

    public ShortLinkRecord getDetails(String code) {
        return repository.findByCode(code).orElseThrow(() -> new LinkNotFoundException(code));
    }

    public ShortLinkRecord getAnalytics(String code) {
        return getDetails(code);
    }

    @Transactional
    public String resolveAndCount(String code) {
        int updated = repository.incrementClick(code, Instant.now());
        if (updated == 0) {
            throw new LinkNotFoundException(code);
        }
        return repository.findLongUrl(code).orElseThrow(() -> new LinkNotFoundException(code));
    }
}
