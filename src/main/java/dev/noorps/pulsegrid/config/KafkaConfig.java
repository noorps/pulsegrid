package dev.noorps.pulsegrid.config;

import dev.noorps.pulsegrid.model.TelemetryEvent;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.ExponentialBackOff;

@Configuration
public class KafkaConfig {
    @Bean
    NewTopic telemetryTopic(@Value("${pulsegrid.topics.telemetry}") String name) {
        return new NewTopic(name, 6, (short) 1);
    }

    @Bean
    NewTopic deadLetterTopic(@Value("${pulsegrid.topics.dead-letter}") String name) {
        return new NewTopic(name, 6, (short) 1);
    }

    @Bean
    DefaultErrorHandler errorHandler(
            KafkaTemplate<Object, Object> template,
            @Value("${pulsegrid.topics.dead-letter}") String deadLetterTopic) {
        ExponentialBackOff backOff = new ExponentialBackOff(200L, 2.0);
        backOff.setMaxInterval(2_000L);
        backOff.setMaxElapsedTime(6_000L);
        var recoverer = new DeadLetterPublishingRecoverer(
                template,
                (record, error) -> new TopicPartition(deadLetterTopic, record.partition()));
        return new DefaultErrorHandler(recoverer, backOff);
    }

    @Bean
    ConcurrentKafkaListenerContainerFactory<String, TelemetryEvent> kafkaListenerContainerFactory(
            ConsumerFactory<String, TelemetryEvent> consumerFactory,
            DefaultErrorHandler errorHandler) {
        var factory = new ConcurrentKafkaListenerContainerFactory<String, TelemetryEvent>();
        factory.setConsumerFactory(consumerFactory);
        factory.setCommonErrorHandler(errorHandler);
        factory.setConcurrency(3);
        return factory;
    }
}
