delimiter $$

CREATE DATABASE `flashover` /*!40100 DEFAULT CHARACTER SET utf8 */$$

delimiter $$

CREATE TABLE `completed` (
  `guid` char(36) NOT NULL,
  `c_images` int(11) NOT NULL,
  `c_binaries` int(11) NOT NULL,
  `c_sounds` int(11) NOT NULL,
  `c_shapes` int(11) NOT NULL,
  `sz_images` int(11) NOT NULL,
  `sz_binaries` int(11) NOT NULL,
  `sz_sounds` int(11) NOT NULL,
  `sz_shapes` int(11) NOT NULL,
  `sz_input` int(11) NOT NULL,
  `cputime` float NOT NULL,
  `waittime` int(11) NOT NULL,
  `timestamp` int(11) NOT NULL,
  `expires` int(11) NOT NULL,
  `user` int(11) NOT NULL,
  `cleaned` tinyint(4) NOT NULL,
  `alias` varchar(45) NOT NULL,
  PRIMARY KEY (`guid`),
  UNIQUE KEY `guid_UNIQUE` (`guid`),
  KEY `userid` (`user`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='Jobs which completed OK.'$$


delimiter $$

CREATE TABLE `incoming` (
  `guid` char(36) NOT NULL,
  `user` int(11) NOT NULL,
  `priority` int(11) NOT NULL,
  `timestamp` int(11) NOT NULL,
  `fetchurl` text,
  PRIMARY KEY (`guid`),
  KEY `priority` (`priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='Incoming job queue.'$$


delimiter $$

CREATE TABLE `user` (
  `id` int(11) NOT NULL,
  `auth_provider` text NOT NULL,
  `auth_id` text NOT NULL,
  `auth_from_ip` text NOT NULL,
  `username` text NOT NULL,
  `email` text NOT NULL,
  `send_email` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8$$
