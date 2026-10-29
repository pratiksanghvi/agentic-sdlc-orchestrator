package com.example.shortener.api;

import com.example.shortener.service.LinkService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RedirectController {

    private final LinkService service;

    public RedirectController(LinkService service) {
        this.service = service;
    }

    @GetMapping("/{code}")
    public ResponseEntity<Void> redirect(@PathVariable String code) {
        String url = service.resolveAndCount(code);
        return ResponseEntity.status(302)
                .header("Location", url)
                .header("Cache-Control", "no-store")
                .build();
    }
}
