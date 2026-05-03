package com.wcp;

import com.wcp.config.MlApiProperties;
import com.wcp.config.WcpProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/**
 * Entry point for the WCP Java business service.
 *
 * <p>Owns: authentication, subscriptions, payment callbacks, content tiering,
 * track-record + share-link APIs. Delegates ML inference to the Python
 * service at {@code wcp-ml-api}, never trains models locally.
 */
@SpringBootApplication
@ConfigurationPropertiesScan
public class WcpApplication {

    public static void main(String[] args) {
        SpringApplication.run(WcpApplication.class, args);
    }
}
