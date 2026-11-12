-- CHECK constraints are enforced by MySQL 8.0.16 and later.
USE tourism_db;

CREATE TABLE destinations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(80) NOT NULL,
    description TEXT
) ENGINE=InnoDB;

CREATE TABLE tour_packages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    destination_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    duration_days INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    available_seats INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_tour_packages_duration CHECK (duration_days > 0),
    CONSTRAINT chk_tour_packages_price CHECK (price > 0),
    CONSTRAINT chk_tour_packages_seats CHECK (available_seats >= 0),
    CONSTRAINT fk_tour_packages_destination
        FOREIGN KEY (destination_id) REFERENCES destinations(id),
    INDEX idx_tour_packages_destination_active (destination_id, is_active)
) ENGINE=InnoDB;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('customer', 'admin') NOT NULL DEFAULT 'customer'
) ENGINE=InnoDB;

CREATE TABLE password_reset_tokens (
    user_id INT PRIMARY KEY,
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
    requested_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    CONSTRAINT fk_password_reset_tokens_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_password_reset_expiry (expires_at)
) ENGINE=InnoDB;
CREATE TABLE bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    package_id INT NOT NULL,
    seats INT NOT NULL,
    trip_date DATE NULL,
    total_price DECIMAL(12, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_bookings_seats CHECK (seats > 0),
    CONSTRAINT chk_bookings_total_price CHECK (total_price >= 0),
    CONSTRAINT chk_bookings_status CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    CONSTRAINT fk_bookings_user
        FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_bookings_package
        FOREIGN KEY (package_id) REFERENCES tour_packages(id),
    INDEX idx_bookings_user_created (user_id, created_at),
    INDEX idx_bookings_package_status (package_id, status),
    INDEX idx_bookings_trip_date (trip_date)
) ENGINE=InnoDB;

CREATE TABLE booking_admin_actions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    admin_user_id INT NOT NULL,
    action_type ENUM('postponed', 'cancelled') NOT NULL,
    previous_trip_date DATE NULL,
    new_trip_date DATE NULL,
    reason VARCHAR(500) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_booking_admin_actions_booking
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE,
    CONSTRAINT fk_booking_admin_actions_admin
        FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_booking_admin_actions_booking_created (booking_id, created_at)
) ENGINE=InnoDB;

INSERT INTO destinations (name, country, description) VALUES
('Jaipur', 'India', 'Historic forts and palaces'),
('Kochi', 'India', 'Coastal city known for its port and heritage'),
('Agra', 'India', 'Home of the Taj Mahal');

INSERT INTO tour_packages
    (destination_id, title, duration_days, price, available_seats)
VALUES
(1, 'Jaipur Heritage Tour', 3, 8500.00, 12),
(2, 'Kochi Coastal Escape', 4, 12000.00, 8),
(3, 'Agra Weekend Visit', 2, 6500.00, 15);
