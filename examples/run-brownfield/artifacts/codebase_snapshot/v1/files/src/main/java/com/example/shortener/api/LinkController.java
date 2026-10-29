package com.example.shortener.api;

import com.example.shortener.persistence.ShortLinkRecord;
import com.example.shortener.service.LinkService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/links")
public class LinkController {

    private final LinkService service;

    public LinkController(LinkService service) {
        this.service = service;
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ShortLinkResponse> create(@RequestBody CreateLinkRequest request) {
        ShortLinkRecord r = service.create(request.url());
        return ResponseEntity.status(201)
                .header("Location", "/api/links/" + r.shortCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(toResponse(r));
    }

    @GetMapping("/{code}")
    public ShortLinkResponse details(@PathVariable String code) {
        return toResponse(service.getDetails(code));
    }

    @GetMapping("/{code}/analytics")
    public LinkAnalyticsResponse analytics(@PathVariable String code) {
        ShortLinkRecord r = service.getAnalytics(code);
        long clicks = r.clickCount();
        Object last = r.lastClickedAt();
        return new LinkAnalyticsResponse(r.shortCode(), clicks, last == null ? null : last.toString());
    }

    private static ShortLinkResponse toResponse(ShortLinkRecord r) {
        Object created = r.createdAt();
        return new ShortLinkResponse(r.shortCode(), r.longUrl(), created == null ? null : created.toString());
    }
}
