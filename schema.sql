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
    FOREIGN KEY (destination_id) REFERENCES destinations(id)
) ENGINE=InnoDB;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    package_id INT NOT NULL,
    seats INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (package_id) REFERENCES tour_packages(id)
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
