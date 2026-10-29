package com.example.shortener;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.context.ApplicationContext;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
public class ServiceReadyListener {

    @EventListener
    public void onReady(ApplicationReadyEvent event) {
        ApplicationContext ctx = event.getApplicationContext();
        if (ctx instanceof WebServerApplicationContext web) {
            int port = web.getWebServer().getPort();
            System.out.println("SERVICE_READY port=" + port);
            System.out.flush();
        }
    }
}
