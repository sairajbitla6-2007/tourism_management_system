-- CHECK constraints are enforced by MySQL 8.0.16 and later.
-- One-time migration for databases created from the previous schema.sql.
-- Take a database backup before running this script.
-- Existing booking totals are estimated from each package's current price;
-- the original historical price cannot be reconstructed if prices changed.

USE tourism_db;

ALTER TABLE users
    ADD COLUMN role ENUM('customer', 'admin') NOT NULL DEFAULT 'customer';

ALTER TABLE bookings
    ADD COLUMN total_price DECIMAL(12, 2) NULL AFTER seats;

UPDATE bookings AS b
JOIN tour_packages AS p ON p.id = b.package_id
SET b.total_price = ROUND(p.price * b.seats, 2)
WHERE b.total_price IS NULL;

ALTER TABLE bookings
    MODIFY COLUMN total_price DECIMAL(12, 2) NOT NULL;

ALTER TABLE tour_packages
    ADD CONSTRAINT chk_tour_packages_duration CHECK (duration_days > 0),
    ADD CONSTRAINT chk_tour_packages_price CHECK (price > 0),
    ADD CONSTRAINT chk_tour_packages_seats CHECK (available_seats >= 0),
    ADD INDEX idx_tour_packages_destination_active (destination_id, is_active);

ALTER TABLE bookings
    ADD CONSTRAINT chk_bookings_seats CHECK (seats > 0),
    ADD CONSTRAINT chk_bookings_total_price CHECK (total_price >= 0),
    ADD INDEX idx_bookings_user_created (user_id, created_at),
    ADD INDEX idx_bookings_package_status (package_id, status);

ALTER TABLE bookings
    ADD CONSTRAINT chk_bookings_status CHECK (status IN ('pending', 'confirmed', 'cancelled'));
