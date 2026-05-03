package com.wcp.repository;

import com.wcp.model.ShareLink;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface ShareLinkRepository extends JpaRepository<ShareLink, Long> {

    Optional<ShareLink> findByShortCode(String shortCode);

    /** Atomic counter increment so concurrent clicks don't lose updates. */
    @Modifying
    @Query("UPDATE ShareLink l SET l.clickCount = l.clickCount + 1 WHERE l.id = :id")
    int incrementClicks(@Param("id") Long id);
}
