-- Add the customer-selected start date to each booking.
-- Existing bookings stay NULL because their original trip date is unknown.
USE tourism_db;

ALTER TABLE bookings
    ADD COLUMN trip_date DATE NULL AFTER seats,
    ADD INDEX idx_bookings_trip_date (trip_date);
