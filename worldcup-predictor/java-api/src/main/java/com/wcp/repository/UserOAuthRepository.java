package com.wcp.repository;

import com.wcp.model.UserOAuth;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserOAuthRepository extends JpaRepository<UserOAuth, Long> {

    Optional<UserOAuth> findByProviderAndProviderUserId(String provider, String providerUserId);

    List<UserOAuth> findByUserId(Long userId);
}
