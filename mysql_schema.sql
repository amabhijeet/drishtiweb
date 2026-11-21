CREATE TABLE IF NOT EXISTS web_reports (
 id VARCHAR(128) PRIMARY KEY, source VARCHAR(32), source_id VARCHAR(128),
 original_lat DOUBLE, original_lon DOUBLE, lat DOUBLE, lon DOUBLE, confidence DOUBLE,
 evidence TEXT, captured VARCHAR(64), title TEXT DEFAULT 'Pothole', description TEXT DEFAULT '',
 place TEXT DEFAULT '', severity TEXT DEFAULT 'Unassessed',
 status VARCHAR(32) DEFAULT 'Draft', gps TEXT DEFAULT 'Valid coordinate format', discrepancy DOUBLE,
 INDEX(status,captured)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS web_media (
 id VARCHAR(128) PRIMARY KEY, report VARCHAR(128), kind VARCHAR(32), name TEXT, data LONGBLOB,
 INDEX(report)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS web_video_clips (
 id VARCHAR(128) PRIMARY KEY, segment_id VARCHAR(128) NOT NULL, title TEXT NOT NULL,
 `start` DOUBLE NOT NULL, `end` DOUBLE NOT NULL, author TEXT NOT NULL,
 created VARCHAR(40) NOT NULL DEFAULT (DATE_FORMAT(UTC_TIMESTAMP(), '%Y-%m-%d %H:%i:%s')),
 INDEX(segment_id,created)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE IF NOT EXISTS web_audit (
 id BIGINT PRIMARY KEY AUTO_INCREMENT,
 at VARCHAR(40) DEFAULT (DATE_FORMAT(UTC_TIMESTAMP(), '%Y-%m-%d %H:%i:%s')),
 actor TEXT, report TEXT, action LONGTEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
