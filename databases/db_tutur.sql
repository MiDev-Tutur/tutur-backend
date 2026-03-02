-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Mar 02, 2026 at 09:34 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `db_tutur`
--

-- --------------------------------------------------------

--
-- Table structure for table `courses`
--

CREATE TABLE `courses` (
  `idCourse` int(11) NOT NULL,
  `idUser` int(11) NOT NULL,
  `idDominantLanguage` int(11) NOT NULL,
  `idLocalLanguage` int(11) NOT NULL,
  `courseStep` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `courses`
--

INSERT INTO `courses` (`idCourse`, `idUser`, `idDominantLanguage`, `idLocalLanguage`, `courseStep`) VALUES
(1, 2, 1, 4, 0);

-- --------------------------------------------------------

--
-- Table structure for table `languages`
--

CREATE TABLE `languages` (
  `idLanguage` int(11) NOT NULL,
  `languageName` varchar(100) NOT NULL,
  `languageType` enum('dominant','local','dialect','') NOT NULL,
  `languageStatus` enum('registered','unregistered','','') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `languages`
--

INSERT INTO `languages` (`idLanguage`, `languageName`, `languageType`, `languageStatus`) VALUES
(1, 'Indonesian', 'dominant', 'registered'),
(2, 'Malay', 'dominant', 'registered'),
(3, 'English', 'dominant', 'registered'),
(4, 'Minang', 'local', 'registered'),
(5, 'Java', 'local', 'registered'),
(6, 'Batak Toba', 'local', 'registered'),
(7, 'Iban', 'local', 'registered'),
(8, 'Sarawak Malay', 'local', 'registered');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `idUser` int(11) NOT NULL,
  `userName` varchar(100) NOT NULL,
  `userEmail` varchar(250) NOT NULL,
  `userPassword` varchar(250) NOT NULL,
  `userParticipantStatus` enum('active','nonactive','','') NOT NULL,
  `userReferenceFolderId` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`idUser`, `userName`, `userEmail`, `userPassword`, `userParticipantStatus`, `userReferenceFolderId`) VALUES
(2, 'admin2', 'admin@gmail.com', '$argon2id$v=19$m=65536,t=3,p=4$i3GOkbJ2TkkJAWCMce5dCw$SDBaE3pKQinQ8aVcveF5Q/T+AcWk1v88/t9wu6BQbXk', 'nonactive', 'folder_7932b2e1');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `courses`
--
ALTER TABLE `courses`
  ADD PRIMARY KEY (`idCourse`);

--
-- Indexes for table `languages`
--
ALTER TABLE `languages`
  ADD PRIMARY KEY (`idLanguage`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`idUser`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `courses`
--
ALTER TABLE `courses`
  MODIFY `idCourse` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `languages`
--
ALTER TABLE `languages`
  MODIFY `idLanguage` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `idUser` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
