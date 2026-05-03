package com.wcp.repository;

import com.wcp.model.UserFavorite;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserFavoriteRepository extends JpaRepository<UserFavorite, Long> {

    Optional<UserFavorite> findByUserIdAndMatchId(Long userId, Long matchId);

    List<UserFavorite> findByUserIdOrderByCreatedAtDesc(Long userId);
}
