package com.example.shortener.api;

import com.example.shortener.service.InvalidUrlException;
import com.example.shortener.service.LinkNotFoundException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.ErrorResponse;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ProblemExceptionHandler {

    private static final Logger LOG = LoggerFactory.getLogger(ProblemExceptionHandler.class);

    @ExceptionHandler(InvalidUrlException.class)
    public ResponseEntity<ProblemDetail> invalidUrl(InvalidUrlException e) {
        return build(HttpStatus.BAD_REQUEST, "url must be an absolute http or https URL");
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ProblemDetail> unreadable(HttpMessageNotReadableException e) {
        return build(HttpStatus.BAD_REQUEST, "request body is missing or malformed");
    }

    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    public ResponseEntity<ProblemDetail> unsupported(HttpMediaTypeNotSupportedException e) {
        return build(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json");
    }

    @ExceptionHandler(LinkNotFoundException.class)
    public ResponseEntity<ProblemDetail> notFound(LinkNotFoundException e) {
        return build(HttpStatus.NOT_FOUND, e.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ProblemDetail> other(Exception e) {
        if (e instanceof ErrorResponse er) {
            HttpStatusCode sc = er.getStatusCode();
            HttpStatus hs = HttpStatus.resolve(sc.value());
            if (hs != null) {
                return build(hs, hs.getReasonPhrase());
            }
        }
        LOG.error("Unhandled exception", e);
        return build(HttpStatus.INTERNAL_SERVER_ERROR, "an unexpected error occurred");
    }

    private static ResponseEntity<ProblemDetail> build(HttpStatus status, String detail) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(status, detail);
        pd.setTitle(status.getReasonPhrase());
        return ResponseEntity.status(status).contentType(MediaType.APPLICATION_PROBLEM_JSON).body(pd);
    }
}
