-- Expand the tour catalogue without duplicating entries if this script is rerun.
-- Existing bookings and package availability are not changed.
USE tourism_db;

INSERT INTO destinations (name, country, description)
SELECT 'Munnar', 'India', 'Tea gardens, misty hills, and cool mountain scenery' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM destinations WHERE name = 'Munnar' AND country = 'India');

INSERT INTO destinations (name, country, description)
SELECT 'Varanasi', 'India', 'Historic riverfront, temples, and cultural heritage' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM destinations WHERE name = 'Varanasi' AND country = 'India');

INSERT INTO destinations (name, country, description)
SELECT 'Udaipur', 'India', 'Lakeside palaces and the heritage of Rajasthan' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM destinations WHERE name = 'Udaipur' AND country = 'India');

INSERT INTO destinations (name, country, description)
SELECT 'Rishikesh', 'India', 'Himalayan foothills, river views, and yoga retreats' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM destinations WHERE name = 'Rishikesh' AND country = 'India');

INSERT INTO destinations (name, country, description)
SELECT 'Darjeeling', 'India', 'Tea estates and views of the eastern Himalayas' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM destinations WHERE name = 'Darjeeling' AND country = 'India');

INSERT INTO tour_packages
    (destination_id, title, duration_days, price, available_seats, is_active)
SELECT d.id, 'Munnar Tea Garden Escape', 3, 9500.00, 12, TRUE
FROM destinations AS d
WHERE d.id = (SELECT MIN(id) FROM destinations WHERE name = 'Munnar' AND country = 'India')
  AND NOT EXISTS (SELECT 1 FROM tour_packages WHERE destination_id = d.id AND title = 'Munnar Tea Garden Escape');

INSERT INTO tour_packages
    (destination_id, title, duration_days, price, available_seats, is_active)
SELECT d.id, 'Varanasi Heritage Visit', 2, 6500.00, 10, TRUE
FROM destinations AS d
WHERE d.id = (SELECT MIN(id) FROM destinations WHERE name = 'Varanasi' AND country = 'India')
  AND NOT EXISTS (SELECT 1 FROM tour_packages WHERE destination_id = d.id AND title = 'Varanasi Heritage Visit');

INSERT INTO tour_packages
    (destination_id, title, duration_days, price, available_seats, is_active)
SELECT d.id, 'Udaipur Lakes and Palaces', 3, 11000.00, 8, TRUE
FROM destinations AS d
WHERE d.id = (SELECT MIN(id) FROM destinations WHERE name = 'Udaipur' AND country = 'India')
  AND NOT EXISTS (SELECT 1 FROM tour_packages WHERE destination_id = d.id AND title = 'Udaipur Lakes and Palaces');

INSERT INTO tour_packages
    (destination_id, title, duration_days, price, available_seats, is_active)
SELECT d.id, 'Rishikesh River and Hills Retreat', 3, 7800.00, 10, TRUE
FROM destinations AS d
WHERE d.id = (SELECT MIN(id) FROM destinations WHERE name = 'Rishikesh' AND country = 'India')
  AND NOT EXISTS (SELECT 1 FROM tour_packages WHERE destination_id = d.id AND title = 'Rishikesh River and Hills Retreat');

INSERT INTO tour_packages
    (destination_id, title, duration_days, price, available_seats, is_active)
SELECT d.id, 'Darjeeling Himalayan Views', 4, 14500.00, 10, TRUE
FROM destinations AS d
WHERE d.id = (SELECT MIN(id) FROM destinations WHERE name = 'Darjeeling' AND country = 'India')
  AND NOT EXISTS (SELECT 1 FROM tour_packages WHERE destination_id = d.id AND title = 'Darjeeling Himalayan Views');
