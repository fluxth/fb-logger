CREATE TABLE IF NOT EXISTS `pings` (
    `ts` timestamp unique primary key not null default (strftime('%s', 'now'))
);

INSERT OR REPLACE INTO `dbconfig` (`key`, `value`) VALUES ('schema_version', '2');
