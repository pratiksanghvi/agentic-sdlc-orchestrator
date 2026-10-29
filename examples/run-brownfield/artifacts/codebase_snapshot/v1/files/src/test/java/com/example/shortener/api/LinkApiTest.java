package com.example.shortener.api;

import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class LinkApiTest {

    private static final Path DB;

    static {
        try {
            DB = Files.createTempFile("shortener-api-test", ".db");
            DB.toFile().deleteOnExit();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> "jdbc:sqlite:" + DB.toAbsolutePath());
    }

    @Autowired
    MockMvc mvc;

    @Autowired
    ObjectMapper mapper;

    private String create(String url) throws Exception {
        String body = mvc.perform(post("/api/links").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"" + url + "\",\"alias\":\"mine\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.longUrl").value(url))
                .andReturn().getResponse().getContentAsString();
        JsonNode n = mapper.readTree(body);
        return n.get("shortCode").asText();
    }

    @Test
    void createAndDetails() throws Exception {
        String code = create("https://example.com/a");
        org.junit.jupiter.api.Assertions.assertNotEquals("mine", code);
        mvc.perform(get("/api/links/" + code))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.shortCode").value(code))
                .andExpect(jsonPath("$.createdAt").exists());
    }

    @Test
    void createSetsLocation() throws Exception {
        String body = mvc.perform(post("/api/links").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"http://example.com\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        String code = mapper.readTree(body).get("shortCode").asText();
        mvc.perform(post("/api/links").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"http://example.com\"}"))
                .andExpect(header().string("Location", org.hamcrest.Matchers.startsWith("/api/links/")));
        org.junit.jupiter.api.Assertions.assertEquals(7, code.length());
    }

    @Test
    void redirectCountsClicks() throws Exception {
        String code = create("https://example.com/r?x=1");
        mvc.perform(get("/api/links/" + code + "/analytics"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.clickCount").value(0))
                .andExpect(jsonPath("$.lastClickedAt").value(nullValue()));
        mvc.perform(get("/" + code))
                .andExpect(status().isFound())
                .andExpect(header().string("Location", "https://example.com/r?x=1"))
                .andExpect(header().string("Cache-Control", "no-store"));
        mvc.perform(get("/" + code)).andExpect(status().isFound());
        mvc.perform(get("/api/links/" + code + "/analytics"))
                .andExpect(jsonPath("$.clickCount").value(2))
                .andExpect(jsonPath("$.lastClickedAt").exists());
    }

    @Test
    void invalidUrlIs400() throws Exception {
        mvc.perform(post("/api/links").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"url\":\"ftp://x.com\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(header().string("Content-Type", "application/problem+json"))
                .andExpect(jsonPath("$.status").value(400));
        mvc.perform(post("/api/links").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void malformedBodyIs400() throws Exception {
        mvc.perform(post("/api/links").contentType(MediaType.APPLICATION_JSON).content("{bad"))
                .andExpect(status().isBadRequest())
                .andExpect(header().string("Content-Type", "application/problem+json"));
        mvc.perform(post("/api/links").contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest());
    }

    @Test
    void wrongContentTypeIs415() throws Exception {
        mvc.perform(post("/api/links").contentType(MediaType.TEXT_PLAIN).content("url"))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(header().string("Content-Type", "application/problem+json"));
    }

    @Test
    void unknownCodeIs404() throws Exception {
        mvc.perform(get("/nope123"))
                .andExpect(status().isNotFound())
                .andExpect(header().string("Content-Type", "application/problem+json"))
                .andExpect(jsonPath("$.title").value("Not Found"));
        mvc.perform(get("/api/links/nope123")).andExpect(status().isNotFound());
        mvc.perform(get("/api/links/nope123/analytics")).andExpect(status().isNotFound());
    }
}
