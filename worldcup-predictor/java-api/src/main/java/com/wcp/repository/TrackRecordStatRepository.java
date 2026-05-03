package com.wcp.repository;

import com.wcp.model.TrackRecordStat;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface TrackRecordStatRepository extends JpaRepository<TrackRecordStat, Long> {

    Optional<TrackRecordStat> findByStatTypeAndPeriod(String statType, String period);

    List<TrackRecordStat> findByPeriod(String period);
}
