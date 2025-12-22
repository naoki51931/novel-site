-- MySQL dump 10.13  Distrib 8.0.44, for Linux (x86_64)
--
-- Host: localhost    Database: novel_db
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `episode_illusts`
--

DROP TABLE IF EXISTS `episode_illusts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `episode_illusts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `episode_id` int NOT NULL,
  `image_url` varchar(255) NOT NULL,
  `position` int NOT NULL,
  `caption` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `episode_id` (`episode_id`),
  KEY `ix_episode_illusts_id` (`id`),
  CONSTRAINT `episode_illusts_ibfk_1` FOREIGN KEY (`episode_id`) REFERENCES `episodes` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `episode_illusts`
--

LOCK TABLES `episode_illusts` WRITE;
/*!40000 ALTER TABLE `episode_illusts` DISABLE KEYS */;
INSERT INTO `episode_illusts` VALUES (1,8,'/static/episode_images/episode_8_illust_1764629685.png',1,NULL,'2025-12-01 22:54:45');
/*!40000 ALTER TABLE `episode_illusts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `episode_likes`
--

DROP TABLE IF EXISTS `episode_likes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `episode_likes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `episode_id` int NOT NULL,
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_episode_likes_episode` (`episode_id`),
  KEY `idx_episode_likes_user` (`user_id`),
  CONSTRAINT `episode_likes_ibfk_1` FOREIGN KEY (`episode_id`) REFERENCES `episodes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `episode_likes_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `episode_likes`
--

LOCK TABLES `episode_likes` WRITE;
/*!40000 ALTER TABLE `episode_likes` DISABLE KEYS */;
INSERT INTO `episode_likes` VALUES (1,8,2,'2025-12-02 04:14:30');
/*!40000 ALTER TABLE `episode_likes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `episode_tags`
--

DROP TABLE IF EXISTS `episode_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `episode_tags` (
  `episode_id` int NOT NULL,
  `tag_id` int NOT NULL,
  PRIMARY KEY (`episode_id`,`tag_id`),
  KEY `tag_id` (`tag_id`),
  CONSTRAINT `episode_tags_ibfk_1` FOREIGN KEY (`episode_id`) REFERENCES `episodes` (`id`) ON DELETE CASCADE,
  CONSTRAINT `episode_tags_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `episode_tags`
--

LOCK TABLES `episode_tags` WRITE;
/*!40000 ALTER TABLE `episode_tags` DISABLE KEYS */;
INSERT INTO `episode_tags` VALUES (7,1),(7,2),(8,2);
/*!40000 ALTER TABLE `episode_tags` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `episodes`
--

DROP TABLE IF EXISTS `episodes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `episodes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `novel_id` int DEFAULT NULL,
  `title` varchar(200) NOT NULL,
  `body` text NOT NULL,
  `episode_number` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `cover_image_url` varchar(255) DEFAULT NULL,
  `view_count` int NOT NULL DEFAULT '0',
  `like_count` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `novel_id` (`novel_id`),
  KEY `ix_episodes_id` (`id`),
  CONSTRAINT `episodes_ibfk_1` FOREIGN KEY (`novel_id`) REFERENCES `novels` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `episodes`
--

LOCK TABLES `episodes` WRITE;
/*!40000 ALTER TABLE `episodes` DISABLE KEYS */;
INSERT INTO `episodes` VALUES (7,6,'テスト','テストテストテスト',1,'2025-11-24 08:18:16',NULL,12,0),(8,7,'テスト百合','テストテストテスト',1,'2025-11-25 07:03:00','/static/episode_images/episode_8_cover.png',53,1);
/*!40000 ALTER TABLE `episodes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `novel_comments`
--

DROP TABLE IF EXISTS `novel_comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `novel_comments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `novel_id` int NOT NULL,
  `user_id` int DEFAULT NULL,
  `body` text NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_novel_comments_id` (`id`),
  KEY `ix_novel_comments_novel_id` (`novel_id`),
  CONSTRAINT `novel_comments_ibfk_1` FOREIGN KEY (`novel_id`) REFERENCES `novels` (`id`),
  CONSTRAINT `novel_comments_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `novel_comments`
--

LOCK TABLES `novel_comments` WRITE;
/*!40000 ALTER TABLE `novel_comments` DISABLE KEYS */;
INSERT INTO `novel_comments` VALUES (1,7,2,'テストコメント','2025-12-06 11:29:54');
/*!40000 ALTER TABLE `novel_comments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `novel_favorites`
--

DROP TABLE IF EXISTS `novel_favorites`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `novel_favorites` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `novel_id` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `novel_id` (`novel_id`),
  KEY `ix_novel_favorites_id` (`id`),
  CONSTRAINT `novel_favorites_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `novel_favorites_ibfk_2` FOREIGN KEY (`novel_id`) REFERENCES `novels` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `novel_favorites`
--

LOCK TABLES `novel_favorites` WRITE;
/*!40000 ALTER TABLE `novel_favorites` DISABLE KEYS */;
/*!40000 ALTER TABLE `novel_favorites` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `novel_likes`
--

DROP TABLE IF EXISTS `novel_likes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `novel_likes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `novel_id` int NOT NULL,
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_novel_likes_novel_id` (`novel_id`),
  KEY `idx_novel_likes_user_id` (`user_id`),
  CONSTRAINT `fk_novel_likes_novel` FOREIGN KEY (`novel_id`) REFERENCES `novels` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_novel_likes_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `novel_likes`
--

LOCK TABLES `novel_likes` WRITE;
/*!40000 ALTER TABLE `novel_likes` DISABLE KEYS */;
INSERT INTO `novel_likes` VALUES (1,7,2,'2025-12-02 05:03:34');
/*!40000 ALTER TABLE `novel_likes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `novel_tags`
--

DROP TABLE IF EXISTS `novel_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `novel_tags` (
  `novel_id` int NOT NULL,
  `tag_id` int NOT NULL,
  PRIMARY KEY (`novel_id`,`tag_id`),
  KEY `tag_id` (`tag_id`),
  CONSTRAINT `novel_tags_ibfk_1` FOREIGN KEY (`novel_id`) REFERENCES `novels` (`id`) ON DELETE CASCADE,
  CONSTRAINT `novel_tags_ibfk_2` FOREIGN KEY (`tag_id`) REFERENCES `tags` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `novel_tags`
--

LOCK TABLES `novel_tags` WRITE;
/*!40000 ALTER TABLE `novel_tags` DISABLE KEYS */;
/*!40000 ALTER TABLE `novel_tags` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `novels`
--

DROP TABLE IF EXISTS `novels`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `novels` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `age_limit` enum('all','r15','r18') NOT NULL DEFAULT 'all',
  `description` text,
  `is_ai_generated` tinyint(1) NOT NULL DEFAULT '0',
  `author_id` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `view_count` int NOT NULL DEFAULT '0',
  `like_count` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  KEY `ix_novels_id` (`id`),
  KEY `ix_novels_title` (`title`),
  CONSTRAINT `novels_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `novels`
--

LOCK TABLES `novels` WRITE;
/*!40000 ALTER TABLE `novels` DISABLE KEYS */;
INSERT INTO `novels` VALUES (6,'テスト','all','テスト',0,1,'2025-11-24 08:18:01',32,0),(7,'テスト百合','all','テスト百合',0,2,'2025-11-25 07:02:40',94,1);
/*!40000 ALTER TABLE `novels` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tags`
--

DROP TABLE IF EXISTS `tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tags` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tags`
--

LOCK TABLES `tags` WRITE;
/*!40000 ALTER TABLE `tags` DISABLE KEYS */;
INSERT INTO `tags` VALUES (1,'バトル'),(2,'百合');
/*!40000 ALTER TABLE `tags` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `is_premium` tinyint(1) NOT NULL DEFAULT '0',
  `email` varchar(255) NOT NULL,
  `birth_date` date DEFAULT NULL,
  `two_factor_code` varchar(6) DEFAULT NULL,
  `two_factor_expires_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_users_username` (`username`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `email_2` (`email`),
  KEY `ix_users_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'demo01','$pbkdf2-sha256$29000$Puc8R4hRao1xzrk3ppTSGg$34RKKFo18Abku.4WLOB8cKVPNiqXKSlYG1g1r3Dq18U',1,'naoki.xyz.ueda.xyz.5@gmail.com',NULL,NULL,NULL),(2,'demo02','$pbkdf2-sha256$29000$EaIU4lzrXWuttRbC.L83hg$BUAiPXLpEW5Pjo3ZBmOXt7pLOtzVXDAHUKi5y70UKqQ',0,'naoki.xyz.ueda.xyz.7@gmail.com',NULL,NULL,NULL),(3,'テスト','$pbkdf2-sha256$29000$PCfknFOq1bp3TgnBeI9xjg$41S8NGnP4ag9lWz2uYaJGNCplE1ch11vKC2Gw8ZTi8w',0,'テスト@example.com',NULL,NULL,NULL),(4,'demo03','$pbkdf2-sha256$29000$YaxVyrn3HgOglLI2BgBgTA$RfxoLsTi62HJJ2zofp9MAE9Al24QTWNPFrdrJHj8IC0',0,'naoki.xyz.ueda.xyz.5+novel@gmail.com',NULL,NULL,NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-12-10  0:36:04
