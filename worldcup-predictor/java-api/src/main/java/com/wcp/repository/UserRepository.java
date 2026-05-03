package com.wcp.repository;

import com.wcp.model.User;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByUuid(UUID uuid);

    Optional<User> findByPhone(String phone);

    Optional<User> findByEmail(String email);

    boolean existsByPhone(String phone);

    boolean existsByEmail(String email);
}
