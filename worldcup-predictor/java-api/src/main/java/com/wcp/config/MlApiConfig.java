package com.wcp.config;

import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

/**
 * RestTemplate bean tuned for calls into the Python ML service.
 *
 * <p>Adds the {@code X-API-Key} header (when configured) plus the project's
 * connect/read timeouts. We use {@link SimpleClientHttpRequestFactory}
 * directly rather than going through {@code RestTemplateBuilder} because the
 * timeout setters on the builder were renamed (
 * {@code setConnectTimeout} / {@code setReadTimeout}) in Spring Boot 3.4 and
 * removed from older versions, so the factory route is the most portable.
 *
 * <p>Inject with {@code @Qualifier("mlApiRestTemplate")} so callers don't
 * accidentally pick up the framework's default RestTemplate bean.
 */
@Configuration
public class MlApiConfig {

    @Bean(name = "mlApiRestTemplate")
    public RestTemplate mlApiRestTemplate(MlApiProperties props) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(props.connectTimeoutMs());
        factory.setReadTimeout(props.readTimeoutMs());

        RestTemplate restTemplate = new RestTemplate(factory);

        // Default headers via interceptor — applies to every outbound request.
        ClientHttpRequestInterceptor headerInterceptor = (request, body, execution) -> {
            if (props.apiKey() != null && !props.apiKey().isBlank()) {
                request.getHeaders().set("X-API-Key", props.apiKey());
            }
            request.getHeaders().setAccept(List.of(MediaType.APPLICATION_JSON));
            return execution.execute(request, body);
        };
        restTemplate.getInterceptors().add(headerInterceptor);

        return restTemplate;
    }
}
