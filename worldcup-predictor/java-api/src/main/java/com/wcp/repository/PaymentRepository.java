package com.wcp.repository;

import com.wcp.model.Payment;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface PaymentRepository extends JpaRepository<Payment, Long> {

    Optional<Payment> findByOrderNo(String orderNo);

    List<Payment> findByUserIdOrderByCreatedAtDesc(Long userId);
}
