-- Store an audit trail for admin-postponed and admin-cancelled bookings.
USE tourism_db;

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
