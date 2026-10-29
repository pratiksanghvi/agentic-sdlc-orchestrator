package com.example.shortener.service;

public class LinkNotFoundException extends RuntimeException {

    private final String code;

    public LinkNotFoundException(String code) {
        super("No short link exists for code '" + code + "'");
        this.code = code;
    }

    public String getCode() {
        return code;
    }
}
