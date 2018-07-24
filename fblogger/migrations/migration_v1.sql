CREATE TABLE IF NOT EXISTS `users` (
    `id` integer unique primary key,
    `fbid` integer unique not null,
    `name` varchar(255) null,
    `username` varchar(255) null,
    `ts` timestamp not null default (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS `logs` (
    `id` integer unique primary key,
    `uid` integer not null,
    `ts` timestamp not null default (strftime('%s', 'now')),
    `lat` integer null,
    `p` integer null,
    `vc` integer null,
    `type` integer not null default 0
);

CREATE TABLE IF NOT EXISTS `dbconfig` (
    `key` varchar(255) unique primary key not null,
    `value` text null
);

INSERT OR REPLACE INTO `dbconfig` (`key`, `value`) VALUES ('schema_version', '1');
