-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jun 14, 2026 at 05:22 PM
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
-- Database: `restaurant_conversational_agent_db`
--

-- --------------------------------------------------------

--
-- Table structure for table `allergen`
--

CREATE TABLE `allergen` (
  `allergen_id` int(11) NOT NULL,
  `allergen_name` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `allergen`
--

INSERT INTO `allergen` (`allergen_id`, `allergen_name`) VALUES
(1, 'Milk'),
(2, 'Egg'),
(3, 'Peanut'),
(4, 'Tree Nuts'),
(5, 'Almond'),
(6, 'Walnut'),
(7, 'Cashew'),
(8, 'Pistachio'),
(9, 'Hazelnut'),
(10, 'Pecan'),
(11, 'Brazil Nut'),
(12, 'Macadamia Nut'),
(13, 'Soy'),
(14, 'Wheat'),
(15, 'Gluten'),
(16, 'Fish'),
(17, 'Shellfish'),
(18, 'Shrimp'),
(19, 'Crab'),
(20, 'Lobster'),
(21, 'Mollusks'),
(22, 'Sesame'),
(23, 'Mustard'),
(24, 'Celery'),
(25, 'Lupin'),
(26, 'Sulfites'),
(27, 'Corn'),
(28, 'Coconut'),
(29, 'Oats'),
(30, 'Barley'),
(31, 'Rye'),
(32, 'Yeast'),
(33, 'Garlic'),
(34, 'Onion'),
(35, 'Tomato'),
(36, 'Mushroom'),
(37, 'Avocado'),
(38, 'Banana'),
(39, 'Kiwi'),
(40, 'Strawberry'),
(41, 'Pineapple'),
(42, 'Mango'),
(43, 'Orange'),
(44, 'Apple'),
(45, 'Peach'),
(46, 'Pear'),
(47, 'Cherry'),
(48, 'Grape'),
(49, 'Watermelon'),
(50, 'Cucumber'),
(51, 'Carrot'),
(52, 'Potato'),
(53, 'Spinach'),
(54, 'Broccoli'),
(55, 'Cauliflower'),
(56, 'Bell Pepper'),
(57, 'Green Peas'),
(58, 'Beans'),
(59, 'Lentils'),
(60, 'Chickpeas'),
(61, 'Black Pepper'),
(62, 'Paprika'),
(63, 'Cinnamon'),
(64, 'Nutmeg'),
(65, 'Cloves'),
(66, 'Cardamom'),
(67, 'Turmeric'),
(68, 'Cumin'),
(69, 'Coriander'),
(70, 'Basil'),
(71, 'Oregano'),
(72, 'Parsley'),
(73, 'Mint'),
(74, 'Rosemary'),
(75, 'Thyme'),
(76, 'Vanilla'),
(77, 'Chocolate'),
(78, 'Cocoa'),
(79, 'Coffee'),
(80, 'Tea'),
(81, 'Honey'),
(82, 'Gelatin'),
(83, 'Beef'),
(84, 'Chicken'),
(85, 'Pork'),
(86, 'Lamb'),
(87, 'Duck'),
(88, 'Turkey'),
(89, 'Salmon'),
(90, 'Tuna'),
(91, 'Cod'),
(92, 'Anchovy'),
(93, 'Sardine'),
(94, 'Squid'),
(95, 'Octopus'),
(96, 'Scallop'),
(97, 'Oyster'),
(98, 'Clam'),
(99, 'Artificial Food Coloring'),
(100, 'Monosodium Glutamate (MSG)');

-- --------------------------------------------------------

--
-- Table structure for table `dietary_type`
--

CREATE TABLE `dietary_type` (
  `dietary_id` int(11) NOT NULL,
  `dietary_name` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `dietary_type`
--

INSERT INTO `dietary_type` (`dietary_id`, `dietary_name`) VALUES
(1, 'Vegetarian'),
(2, 'Vegan'),
(3, 'Pescatarian'),
(4, 'Flexitarian'),
(5, 'Keto'),
(6, 'Low Carb'),
(7, 'High Protein'),
(8, 'Low Fat'),
(9, 'Low Sodium'),
(10, 'Gluten Free'),
(11, 'Dairy Free'),
(12, 'Egg Free'),
(13, 'Nut Free'),
(14, 'Peanut Free'),
(15, 'Soy Free'),
(16, 'Shellfish Free'),
(17, 'Fish Free'),
(18, 'Wheat Free'),
(19, 'Sugar Free'),
(20, 'Low Sugar'),
(21, 'Organic'),
(22, 'Whole Food'),
(23, 'Plant Based'),
(24, 'Raw Vegan'),
(25, 'Mediterranean Diet'),
(26, 'Paleo'),
(27, 'Carnivore'),
(28, 'Diabetic Friendly'),
(29, 'Heart Healthy'),
(30, 'Weight Loss'),
(31, 'Weight Gain'),
(32, 'Athlete Friendly'),
(33, 'Bodybuilding'),
(34, 'Muscle Building'),
(35, 'Low Cholesterol'),
(36, 'Low Calorie'),
(37, 'High Fiber'),
(38, 'Low Fiber'),
(39, 'Halal'),
(40, 'Kosher'),
(41, 'Jain'),
(42, 'Buddhist Vegetarian'),
(43, 'Lacto Vegetarian'),
(44, 'Ovo Vegetarian'),
(45, 'Lacto Ovo Vegetarian'),
(46, 'Fruitarian'),
(47, 'Macrobiotic'),
(48, 'Anti Inflammatory'),
(49, 'Gut Friendly'),
(50, 'Balanced Diet'),
(51, 'Pregnancy Friendly'),
(52, 'Kid Friendly'),
(53, 'Senior Friendly'),
(54, 'Immune Boosting'),
(55, 'Detox Diet'),
(56, 'Clean Eating'),
(57, 'Whole30'),
(58, 'Dash Diet'),
(59, 'Low Glycemic'),
(60, 'High Energy'),
(61, 'Sports Nutrition'),
(62, 'Post Workout'),
(63, 'Pre Workout'),
(64, 'Brain Healthy'),
(65, 'Bone Healthy'),
(66, 'Iron Rich'),
(67, 'Calcium Rich'),
(68, 'Vitamin C Rich'),
(69, 'Vitamin D Rich'),
(70, 'Protein Rich'),
(71, 'Omega 3 Rich'),
(72, 'Low Purine'),
(73, 'GERD Friendly'),
(74, 'Ulcer Friendly'),
(75, 'Renal Friendly'),
(76, 'Liver Friendly'),
(77, 'Low Potassium'),
(78, 'Low Phosphorus'),
(79, 'Low Oxalate'),
(80, 'Low Histamine'),
(81, 'AIP Diet'),
(82, 'FODMAP Friendly'),
(83, 'Low FODMAP'),
(84, 'Nightshade Free'),
(85, 'Legume Free'),
(86, 'Corn Free'),
(87, 'Seed Free'),
(88, 'Caffeine Free'),
(89, 'Alcohol Free'),
(90, 'Artificial Sweetener Free'),
(91, 'Preservative Free'),
(92, 'Additive Free'),
(93, 'MSG Free'),
(94, 'Eco Friendly'),
(95, 'Sustainable Choice'),
(96, 'Locally Sourced'),
(97, 'Farm to Table'),
(98, 'Seasonal Menu'),
(99, 'Chef Recommended'),
(100, 'Customizable Diet');

-- --------------------------------------------------------

--
-- Table structure for table `ingredient`
--

CREATE TABLE `ingredient` (
  `ingredient_id` int(11) NOT NULL,
  `ingredient_name` text NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `ingredient`
--

INSERT INTO `ingredient` (`ingredient_id`, `ingredient_name`) VALUES
(1, 'Chicken Breast'),
(2, 'Beef'),
(3, 'Pork'),
(4, 'Fish'),
(5, 'Shrimp'),
(6, 'Crab'),
(7, 'Lobster'),
(8, 'Egg'),
(9, 'Milk'),
(10, 'Cheddar Cheese'),
(11, 'Mozzarella Cheese'),
(12, 'Parmesan Cheese'),
(13, 'Butter'),
(14, 'Yogurt'),
(15, 'Cream'),
(16, 'Rice'),
(17, 'Basmati Rice'),
(18, 'Brown Rice'),
(19, 'Pasta'),
(20, 'Noodles'),
(21, 'Bread'),
(22, 'Burger Bun'),
(23, 'Pizza Dough'),
(24, 'Flour'),
(25, 'Tomato'),
(26, 'Tomato Sauce'),
(27, 'Potato'),
(28, 'Sweet Potato'),
(29, 'Onion'),
(30, 'Garlic'),
(31, 'Ginger'),
(32, 'Carrot'),
(33, 'Cucumber'),
(34, 'Lettuce'),
(35, 'Spinach'),
(36, 'Cabbage'),
(37, 'Broccoli'),
(38, 'Cauliflower'),
(39, 'Bell Pepper'),
(40, 'Green Chili'),
(41, 'Mushroom'),
(42, 'Corn'),
(43, 'Green Beans'),
(44, 'Peas'),
(45, 'Avocado'),
(46, 'Olives'),
(47, 'Lemon'),
(48, 'Lime'),
(49, 'Orange'),
(50, 'Apple'),
(51, 'Banana'),
(52, 'Mango'),
(53, 'Pineapple'),
(54, 'Strawberry'),
(55, 'Blueberry'),
(56, 'Coconut Milk'),
(57, 'Coconut'),
(58, 'Peanut'),
(59, 'Almond'),
(60, 'Cashew'),
(61, 'Walnut'),
(62, 'Sesame Seeds'),
(63, 'Soy Sauce'),
(64, 'Vinegar'),
(65, 'Olive Oil'),
(66, 'Vegetable Oil'),
(67, 'Salt'),
(68, 'Black Pepper'),
(69, 'Paprika'),
(70, 'Turmeric'),
(71, 'Cumin'),
(72, 'Coriander Powder'),
(73, 'Curry Powder'),
(74, 'Cinnamon'),
(75, 'Cardamom'),
(76, 'Cloves'),
(77, 'Nutmeg'),
(78, 'Bay Leaf'),
(79, 'Parsley'),
(80, 'Cilantro'),
(81, 'Basil'),
(82, 'Oregano'),
(83, 'Thyme'),
(84, 'Rosemary'),
(85, 'Mint'),
(86, 'Sugar'),
(87, 'Brown Sugar'),
(88, 'Honey'),
(89, 'Chocolate'),
(90, 'Cocoa Powder'),
(91, 'Vanilla Extract'),
(92, 'Baking Powder'),
(93, 'Yeast'),
(94, 'Ice Cream'),
(95, 'Coffee Beans'),
(96, 'Tea Leaves'),
(97, 'Orange Juice'),
(98, 'Mayonnaise'),
(99, 'Mustard'),
(100, 'Ketchup');

-- --------------------------------------------------------

--
-- Table structure for table `item_allergen`
--

CREATE TABLE `item_allergen` (
  `item_id` int(11) NOT NULL,
  `allergen_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `item_allergen`
--

INSERT INTO `item_allergen` (`item_id`, `allergen_id`) VALUES
(1, 1),
(1, 14),
(2, 1),
(2, 14),
(3, 1),
(3, 14),
(4, 1),
(4, 14),
(5, 1),
(5, 14),
(6, 1),
(6, 14),
(7, 1),
(7, 14),
(8, 14),
(9, 26),
(10, 14),
(11, 1),
(11, 14),
(12, 1),
(12, 14),
(13, 26),
(14, 14),
(15, 1),
(15, 2),
(16, 1),
(17, 35),
(18, 1),
(19, 1),
(20, 24),
(21, 1),
(22, 16),
(22, 17),
(23, 1),
(23, 14),
(24, 1),
(24, 14),
(25, 14),
(26, 1),
(26, 16),
(27, 2),
(27, 13),
(28, 13),
(29, 2),
(29, 16),
(30, 2),
(31, 14),
(32, 1),
(32, 14),
(33, 14),
(34, 14),
(34, 17),
(35, 23),
(36, 23),
(37, 16),
(38, 23),
(39, 23),
(40, 16),
(41, 26),
(42, 16),
(43, 1),
(43, 14),
(44, 14),
(44, 16),
(45, 14),
(46, 1),
(46, 14),
(47, 1),
(47, 14),
(48, 14),
(49, 1),
(49, 2),
(49, 14),
(50, 1),
(50, 2),
(51, 1),
(51, 2),
(51, 14),
(52, 1),
(52, 2),
(53, 28),
(54, 1),
(54, 14),
(55, 1),
(56, 1),
(57, 1),
(58, 1),
(59, 43),
(60, 43),
(61, 26),
(62, 1),
(63, 1),
(64, 1),
(65, 1),
(66, 80),
(67, 14),
(68, 14),
(69, 14),
(70, 14),
(71, 1),
(71, 14),
(72, 1),
(72, 14),
(73, 16),
(74, 16),
(75, 13),
(75, 14),
(76, 17),
(77, 14),
(77, 58),
(78, 28),
(79, 14),
(80, 13),
(81, 13),
(82, 13),
(82, 14),
(83, 1),
(84, 23),
(85, 23),
(86, 1),
(86, 14),
(87, 25),
(88, 22),
(89, 22),
(90, 26),
(91, 26),
(92, 17),
(93, 17),
(94, 14),
(94, 16),
(95, 1),
(95, 2),
(96, 1),
(96, 2),
(96, 14),
(97, 1),
(97, 2),
(98, 1),
(98, 2),
(98, 14),
(99, 14),
(100, 1);

-- --------------------------------------------------------

--
-- Table structure for table `item_dietary`
--

CREATE TABLE `item_dietary` (
  `item_id` int(11) NOT NULL,
  `dietary_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `item_dietary`
--

INSERT INTO `item_dietary` (`item_id`, `dietary_id`) VALUES
(1, 1),
(1, 43),
(2, 43),
(3, 7),
(4, 1),
(4, 23),
(5, 7),
(6, 7),
(7, 33),
(8, 1),
(8, 23),
(9, 1),
(10, 1),
(11, 1),
(12, 1),
(13, 7),
(14, 1),
(14, 23),
(15, 1),
(15, 36),
(16, 1),
(16, 25),
(17, 1),
(17, 23),
(17, 36),
(18, 7),
(18, 29),
(19, 1),
(19, 36),
(20, 7),
(21, 1),
(22, 3),
(22, 29),
(23, 7),
(24, 7),
(25, 1),
(25, 23),
(26, 3),
(27, 7),
(28, 1),
(28, 23),
(29, 3),
(30, 1),
(31, 7),
(32, 1),
(33, 1),
(33, 23),
(34, 3),
(35, 7),
(36, 7),
(37, 3),
(38, 1),
(38, 23),
(38, 36),
(39, 7),
(39, 29),
(40, 3),
(40, 29),
(41, 33),
(42, 33),
(43, 7),
(44, 3),
(45, 1),
(45, 23),
(46, 7),
(47, 7),
(48, 1),
(48, 23),
(49, 1),
(50, 1),
(51, 1),
(52, 1),
(53, 2),
(53, 23),
(53, 36),
(54, 1),
(55, 1),
(56, 1),
(57, 1),
(58, 2),
(58, 23),
(59, 2),
(59, 23),
(59, 36),
(60, 2),
(60, 23),
(60, 36),
(61, 2),
(61, 88),
(62, 2),
(62, 88),
(63, 1),
(64, 1),
(65, 2),
(65, 88),
(66, 2),
(66, 88),
(67, 7),
(68, 7),
(69, 7),
(70, 7),
(71, 7),
(72, 1),
(73, 3),
(74, 3),
(75, 7),
(76, 3),
(77, 1),
(78, 25),
(79, 7),
(80, 7),
(81, 7),
(82, 1),
(83, 7),
(84, 7),
(85, 1),
(85, 23),
(86, 1),
(87, 2),
(87, 23),
(88, 2),
(88, 23),
(89, 7),
(90, 33),
(91, 33),
(92, 3),
(93, 3),
(94, 3),
(95, 7),
(96, 1),
(97, 1),
(97, 36),
(98, 1),
(99, 2),
(99, 23),
(99, 36),
(100, 99);

-- --------------------------------------------------------

--
-- Table structure for table `menu_ingredient`
--

CREATE TABLE `menu_ingredient` (
  `item_id` int(11) NOT NULL,
  `ingredient_id` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `menu_ingredient`
--

INSERT INTO `menu_ingredient` (`item_id`, `ingredient_id`) VALUES
(1, 11),
(1, 23),
(1, 25),
(2, 11),
(2, 23),
(2, 26),
(3, 1),
(3, 11),
(3, 23),
(4, 34),
(4, 39),
(4, 41),
(5, 2),
(5, 10),
(5, 22),
(6, 1),
(6, 22),
(6, 34),
(7, 2),
(7, 10),
(7, 22),
(8, 22),
(8, 34),
(8, 45),
(9, 27),
(9, 67),
(10, 24),
(10, 29),
(10, 98),
(11, 13),
(11, 21),
(11, 30),
(12, 11),
(12, 24),
(13, 1),
(13, 66),
(13, 68),
(14, 24),
(14, 32),
(14, 36),
(15, 34),
(15, 68),
(16, 33),
(16, 34),
(16, 46),
(17, 25),
(17, 33),
(17, 34),
(18, 1),
(18, 34),
(18, 98),
(19, 15),
(19, 25),
(20, 1),
(20, 29),
(21, 15),
(21, 41),
(22, 5),
(22, 25),
(23, 2),
(23, 19),
(23, 26),
(24, 1),
(24, 15),
(24, 19),
(25, 19),
(25, 32),
(25, 39),
(26, 5),
(26, 15),
(26, 19),
(27, 1),
(27, 8),
(27, 16),
(28, 16),
(28, 32),
(28, 42),
(29, 5),
(29, 8),
(29, 16),
(30, 8),
(30, 16),
(30, 29),
(31, 1),
(31, 21),
(31, 29),
(32, 11),
(32, 21),
(32, 29),
(33, 21),
(33, 29),
(33, 32),
(34, 5),
(34, 21),
(34, 29),
(35, 1),
(35, 73),
(36, 2),
(36, 73),
(37, 4),
(37, 73),
(38, 32),
(38, 73);

-- --------------------------------------------------------

--
-- Table structure for table `menu_item`
--

CREATE TABLE `menu_item` (
  `item_id` int(11) NOT NULL,
  `item_name` text NOT NULL,
  `category` text DEFAULT NULL,
  `description` text DEFAULT NULL,
  `price` double DEFAULT NULL,
  `calories` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `menu_item`
--

INSERT INTO `menu_item` (`item_id`, `item_name`, `category`, `description`, `price`, `calories`) VALUES
(1, 'Margherita Pizza', 'Pizza', 'Classic pizza with tomato and mozzarella', 8.99, 650),
(2, 'Pepperoni Pizza', 'Pizza', 'Pizza topped with pepperoni slices', 10.99, 750),
(3, 'BBQ Chicken Pizza', 'Pizza', 'Pizza with BBQ chicken and cheese', 11.99, 800),
(4, 'Veggie Pizza', 'Pizza', 'Pizza with mixed vegetables', 9.99, 620),
(5, 'Cheese Burger', 'Burger', 'Beef burger with cheese', 7.99, 700),
(6, 'Chicken Burger', 'Burger', 'Grilled chicken burger', 7.49, 650),
(7, 'Double Burger', 'Burger', 'Double beef patty burger', 10.49, 950),
(8, 'Veggie Burger', 'Burger', 'Plant-based burger', 6.99, 550),
(9, 'French Fries', 'Sides', 'Crispy potato fries', 3.99, 350),
(10, 'Onion Rings', 'Sides', 'Deep fried onion rings', 4.49, 400),
(11, 'Garlic Bread', 'Appetizer', 'Toasted bread with garlic butter', 4.99, 300),
(12, 'Mozzarella Sticks', 'Appetizer', 'Fried mozzarella cheese sticks', 5.99, 450),
(13, 'Chicken Wings', 'Appetizer', 'Spicy chicken wings', 8.49, 600),
(14, 'Spring Rolls', 'Appetizer', 'Vegetable spring rolls', 5.49, 250),
(15, 'Caesar Salad', 'Salad', 'Romaine lettuce with Caesar dressing', 6.99, 320),
(16, 'Greek Salad', 'Salad', 'Salad with feta cheese and olives', 7.49, 290),
(17, 'Garden Salad', 'Salad', 'Fresh mixed vegetables', 5.99, 220),
(18, 'Chicken Salad', 'Salad', 'Salad topped with grilled chicken', 8.49, 380),
(19, 'Tomato Soup', 'Soup', 'Creamy tomato soup', 4.99, 180),
(20, 'Chicken Soup', 'Soup', 'Traditional chicken soup', 5.49, 220),
(21, 'Mushroom Soup', 'Soup', 'Creamy mushroom soup', 5.99, 240),
(22, 'Seafood Soup', 'Soup', 'Soup with mixed seafood', 7.99, 300),
(23, 'Spaghetti Bolognese', 'Pasta', 'Pasta with meat sauce', 10.99, 700),
(24, 'Chicken Alfredo', 'Pasta', 'Creamy Alfredo pasta with chicken', 11.49, 750),
(25, 'Vegetable Pasta', 'Pasta', 'Pasta with fresh vegetables', 9.49, 550),
(26, 'Seafood Pasta', 'Pasta', 'Pasta with shrimp and fish', 12.99, 720),
(27, 'Fried Rice', 'Rice', 'Chicken fried rice', 8.99, 650),
(28, 'Vegetable Fried Rice', 'Rice', 'Vegetable fried rice', 7.99, 520),
(29, 'Seafood Fried Rice', 'Rice', 'Seafood mixed fried rice', 10.99, 700),
(30, 'Egg Fried Rice', 'Rice', 'Rice with egg and vegetables', 7.49, 550),
(31, 'Chicken Kottu', 'Sri Lankan', 'Chopped roti with chicken', 8.99, 850),
(32, 'Cheese Kottu', 'Sri Lankan', 'Kottu with cheese', 9.49, 900),
(33, 'Vegetable Kottu', 'Sri Lankan', 'Vegetable kottu roti', 7.99, 700),
(34, 'Seafood Kottu', 'Sri Lankan', 'Seafood kottu special', 10.99, 950),
(35, 'Chicken Curry', 'Curry', 'Spicy chicken curry', 8.49, 450),
(36, 'Beef Curry', 'Curry', 'Traditional beef curry', 9.49, 500),
(37, 'Fish Curry', 'Curry', 'Sri Lankan fish curry', 8.99, 400),
(38, 'Vegetable Curry', 'Curry', 'Mixed vegetable curry', 6.99, 250),
(39, 'Grilled Chicken', 'Grill', 'Herb grilled chicken breast', 10.99, 500),
(40, 'Grilled Fish', 'Grill', 'Fresh grilled fish fillet', 11.99, 450),
(41, 'BBQ Ribs', 'Grill', 'Barbecue pork ribs', 13.99, 850),
(42, 'Mixed Grill', 'Grill', 'Assorted grilled meats', 15.99, 1000),
(43, 'Club Sandwich', 'Sandwich', 'Triple-layer chicken sandwich', 7.99, 600),
(44, 'Tuna Sandwich', 'Sandwich', 'Tuna and lettuce sandwich', 6.99, 450),
(45, 'Veg Sandwich', 'Sandwich', 'Vegetable sandwich', 5.99, 350),
(46, 'Chicken Wrap', 'Wrap', 'Chicken wrap with vegetables', 7.49, 500),
(47, 'Beef Wrap', 'Wrap', 'Beef wrap with sauce', 8.49, 620),
(48, 'Veggie Wrap', 'Wrap', 'Healthy vegetable wrap', 6.49, 380),
(49, 'Chocolate Cake', 'Dessert', 'Rich chocolate cake', 4.99, 450),
(50, 'Cheesecake', 'Dessert', 'Creamy cheesecake', 5.49, 420),
(51, 'Brownie', 'Dessert', 'Chocolate brownie', 3.99, 350),
(52, 'Ice Cream Sundae', 'Dessert', 'Ice cream with toppings', 4.49, 400),
(53, 'Fruit Salad', 'Dessert', 'Fresh fruit mix', 3.99, 180),
(54, 'Apple Pie', 'Dessert', 'Traditional apple pie', 4.99, 320),
(55, 'Vanilla Milkshake', 'Beverage', 'Vanilla flavored milkshake', 3.99, 350),
(56, 'Chocolate Milkshake', 'Beverage', 'Chocolate milkshake', 4.49, 420),
(57, 'Strawberry Milkshake', 'Beverage', 'Strawberry milkshake', 4.49, 390),
(58, 'Mango Smoothie', 'Beverage', 'Fresh mango smoothie', 4.99, 280),
(59, 'Orange Juice', 'Beverage', 'Fresh orange juice', 3.49, 120),
(60, 'Lemon Juice', 'Beverage', 'Fresh lemon juice', 2.99, 90),
(61, 'Iced Tea', 'Beverage', 'Refreshing iced tea', 2.99, 80),
(62, 'Coffee', 'Beverage', 'Hot brewed coffee', 2.49, 15),
(63, 'Cappuccino', 'Beverage', 'Coffee with milk foam', 3.49, 120),
(64, 'Latte', 'Beverage', 'Creamy latte coffee', 3.99, 180),
(65, 'Espresso', 'Beverage', 'Strong espresso shot', 2.29, 10),
(66, 'Green Tea', 'Beverage', 'Healthy green tea', 2.49, 5),
(67, 'Chicken Nuggets', 'Fast Food', 'Crispy chicken nuggets', 5.99, 450),
(68, 'Hot Dog', 'Fast Food', 'Classic hot dog', 4.99, 380),
(69, 'Taco', 'Mexican', 'Beef taco with vegetables', 3.99, 250),
(70, 'Chicken Taco', 'Mexican', 'Chicken taco special', 4.49, 280),
(71, 'Burrito', 'Mexican', 'Stuffed beef burrito', 7.99, 650),
(72, 'Nachos', 'Mexican', 'Cheesy nachos', 6.49, 500),
(73, 'Sushi Roll', 'Japanese', 'Fresh sushi roll', 8.99, 300),
(74, 'Salmon Sushi', 'Japanese', 'Salmon sushi pieces', 10.99, 350),
(75, 'Ramen', 'Japanese', 'Japanese noodle soup', 9.99, 550),
(76, 'Tempura', 'Japanese', 'Crispy shrimp tempura', 8.49, 450),
(77, 'Pad Thai', 'Thai', 'Thai stir-fried noodles', 9.49, 600),
(78, 'Thai Curry', 'Thai', 'Traditional Thai curry', 10.49, 500),
(79, 'Dim Sum', 'Chinese', 'Steamed dumplings', 7.49, 320),
(80, 'Sweet and Sour Chicken', 'Chinese', 'Chicken in sweet sour sauce', 9.99, 650),
(81, 'Kung Pao Chicken', 'Chinese', 'Spicy Chinese chicken', 10.49, 680),
(82, 'Chow Mein', 'Chinese', 'Stir-fried noodles', 8.99, 600),
(83, 'Butter Chicken', 'Indian', 'Creamy butter chicken curry', 11.49, 700),
(84, 'Chicken Biryani', 'Indian', 'Spiced rice with chicken', 10.99, 800),
(85, 'Vegetable Biryani', 'Indian', 'Vegetarian biryani', 8.99, 650),
(86, 'Naan Bread', 'Indian', 'Traditional naan bread', 2.99, 220),
(87, 'Falafel', 'Middle Eastern', 'Fried chickpea balls', 6.49, 340),
(88, 'Hummus Plate', 'Middle Eastern', 'Hummus with pita bread', 5.99, 280),
(89, 'Shawarma', 'Middle Eastern', 'Chicken shawarma wrap', 7.99, 600),
(90, 'Steak', 'Main Course', 'Grilled beef steak', 15.99, 850),
(91, 'Ribeye Steak', 'Main Course', 'Premium ribeye steak', 18.99, 950),
(92, 'Lobster Tail', 'Seafood', 'Grilled lobster tail', 22.99, 500),
(93, 'Shrimp Platter', 'Seafood', 'Seasoned shrimp platter', 14.99, 550),
(94, 'Fish and Chips', 'Seafood', 'Fried fish with fries', 11.99, 700),
(95, 'Breakfast Combo', 'Breakfast', 'Eggs, toast and sausage', 7.99, 650),
(96, 'Pancakes', 'Breakfast', 'Stack of pancakes', 5.99, 450),
(97, 'Omelette', 'Breakfast', 'Cheese omelette', 4.99, 300),
(98, 'French Toast', 'Breakfast', 'Classic French toast', 5.49, 400),
(99, 'Avocado Toast', 'Breakfast', 'Toast with avocado spread', 6.49, 350),
(100, 'Chef Special Platter', 'Special', 'Mixed signature dishes', 19.99, 1200);

-- --------------------------------------------------------

--
-- Table structure for table `restaurant_policy`
--

CREATE TABLE `restaurant_policy` (
  `policy_id` int(11) NOT NULL,
  `policy_name` text NOT NULL,
  `policy_description` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `restaurant_policy`
--

INSERT INTO `restaurant_policy` (`policy_id`, `policy_name`, `policy_description`) VALUES
(1, 'No Smoking', 'Smoking is prohibited inside the restaurant premises.'),
(2, 'Pet Friendly', 'Customers may bring well-behaved pets to designated areas.'),
(3, 'Free WiFi', 'Complimentary WiFi is available for all customers.'),
(4, 'Reservations Required', 'Advance reservations are required for dining.'),
(5, 'Walk-Ins Welcome', 'Walk-in customers are accepted without reservations.'),
(6, 'Takeaway Available', 'Food can be ordered for takeaway.'),
(7, 'Delivery Available', 'Food delivery service is provided.'),
(8, 'Cash Only', 'Only cash payments are accepted.'),
(9, 'Card Payments Accepted', 'Credit and debit card payments are accepted.'),
(10, 'Mobile Payments Accepted', 'Digital wallet and mobile payments are accepted.'),
(11, 'No Outside Food', 'Outside food and beverages are not permitted.'),
(12, 'Family Friendly', 'The restaurant welcomes families with children.'),
(13, 'Kids Menu Available', 'Special menu options are available for children.'),
(14, 'Wheelchair Accessible', 'Facilities are accessible for wheelchair users.'),
(15, 'Accessible Restrooms', 'Accessible restroom facilities are available.'),
(16, 'Outdoor Seating', 'Customers can dine in outdoor seating areas.'),
(17, 'Indoor Seating', 'Indoor seating is available.'),
(18, 'Dress Code Casual', 'Casual attire is permitted.'),
(19, 'Dress Code Formal', 'Formal attire is required.'),
(20, 'Buffet Service', 'Buffet-style dining service is offered.'),
(21, 'Self Service', 'Customers order and collect food themselves.'),
(22, 'Table Service', 'Food is served directly to tables by staff.'),
(23, 'Alcohol Served', 'Alcoholic beverages are available.'),
(24, 'No Alcohol Served', 'Alcoholic beverages are not available.'),
(25, 'Halal Certified', 'All food served is Halal certified.'),
(26, 'Kosher Certified', 'Food preparation follows Kosher standards.'),
(27, 'Vegetarian Options', 'Vegetarian menu items are available.'),
(28, 'Vegan Options', 'Vegan menu items are available.'),
(29, 'Gluten Free Options', 'Gluten-free dishes are available.'),
(30, 'Nut Free Kitchen', 'No nuts are used in food preparation.'),
(31, 'Dairy Free Options', 'Dairy-free menu items are available.'),
(32, 'Allergy Information Available', 'Detailed allergy information is provided.'),
(33, 'Locally Sourced Ingredients', 'Ingredients are sourced from local suppliers.'),
(34, 'Organic Ingredients', 'Organic ingredients are used whenever possible.'),
(35, 'Sustainable Seafood', 'Seafood is sourced from sustainable fisheries.'),
(36, 'Food Waste Reduction', 'Measures are taken to minimize food waste.'),
(37, 'Reusable Packaging', 'Reusable packaging options are encouraged.'),
(38, 'Recyclable Packaging', 'Packaging materials are recyclable.'),
(39, 'Compostable Packaging', 'Packaging materials are compostable.'),
(40, 'Contactless Ordering', 'Orders can be placed without direct contact.'),
(41, 'Contactless Payment', 'Payments can be made without physical contact.'),
(42, 'Online Reservations', 'Reservations can be made online.'),
(43, 'Online Ordering', 'Food can be ordered through online platforms.'),
(44, 'Late Night Service', 'Restaurant operates late into the night.'),
(45, '24 Hour Service', 'Restaurant is open 24 hours a day.'),
(46, 'Live Music', 'Live music performances are hosted regularly.'),
(47, 'Private Dining Rooms', 'Private dining rooms are available.'),
(48, 'Event Hosting', 'Restaurant can host private events and functions.'),
(49, 'Birthday Packages', 'Special birthday celebration packages are offered.'),
(50, 'Corporate Catering', 'Catering services are available for businesses.'),
(51, 'Minimum Order Requirement', 'A minimum order amount may apply.'),
(52, 'Service Charge Applied', 'A service charge is added to bills.'),
(53, 'No Service Charge', 'No service charge is applied.'),
(54, 'Refund Policy Available', 'Refunds are provided according to policy terms.'),
(55, 'No Refunds', 'Refunds are generally not available.'),
(56, 'Cancellation Policy', 'Reservation cancellations are subject to conditions.'),
(57, 'Group Booking Discount', 'Discounts are available for large groups.'),
(58, 'Student Discount', 'Students receive special discounts.'),
(59, 'Senior Citizen Discount', 'Senior citizens receive discounted pricing.'),
(60, 'Loyalty Program', 'Frequent customers can join a loyalty program.'),
(61, 'Membership Benefits', 'Members receive exclusive offers and rewards.'),
(62, 'Seasonal Menu', 'Menu changes based on seasonal ingredients.'),
(63, 'Chef Specials', 'Special dishes are prepared by the chef.'),
(64, 'Customizable Orders', 'Customers can customize menu items.'),
(65, 'Spice Level Customization', 'Customers can select preferred spice levels.'),
(66, 'Nutrition Information Available', 'Nutritional details are provided for menu items.'),
(67, 'Calorie Information Available', 'Calorie counts are displayed on menus.'),
(68, 'Open Kitchen', 'Customers can view food preparation areas.'),
(69, 'No Photography', 'Photography is not permitted inside the restaurant.'),
(70, 'Photography Allowed', 'Customers may take photos freely.'),
(71, 'Quiet Dining Environment', 'Noise levels are kept low for comfort.'),
(72, 'Family Events Welcome', 'Family gatherings and celebrations are encouraged.'),
(73, 'Business Meetings Welcome', 'Facilities support business meetings.'),
(74, 'Study Friendly', 'Customers may study or work while dining.'),
(75, 'Power Outlets Available', 'Electrical outlets are available for customers.'),
(76, 'Free Parking', 'Complimentary parking is available.'),
(77, 'Valet Parking', 'Valet parking service is provided.'),
(78, 'Street Parking Only', 'Parking is limited to nearby streets.'),
(79, 'Bike Parking Available', 'Bicycle parking facilities are available.'),
(80, 'Security Surveillance', 'Security cameras operate throughout the premises.'),
(81, 'Cashless Preferred', 'Digital payment methods are encouraged.'),
(82, 'Eco Friendly Operations', 'Environmentally friendly business practices are followed.'),
(83, 'Renewable Energy Usage', 'Renewable energy sources are utilized.'),
(84, 'Community Support Program', 'The restaurant supports local community initiatives.'),
(85, 'Employee Wellness Program', 'Staff wellness and health programs are maintained.'),
(86, 'Food Donation Program', 'Surplus food is donated to charities.'),
(87, 'Locally Owned Business', 'The restaurant is independently locally owned.'),
(88, 'Franchise Operation', 'The restaurant operates as part of a franchise.'),
(89, 'Reservation Deposit Required', 'A deposit is required to confirm reservations.'),
(90, 'Peak Hour Time Limit', 'Dining time limits may apply during busy periods.'),
(91, 'No Minimum Spend', 'There is no minimum spending requirement.'),
(92, 'Private Parking Available', 'Dedicated parking spaces are available.'),
(93, 'Drive Through Service', 'Customers can order and collect food via drive-through.'),
(94, 'Curbside Pickup', 'Orders can be collected without entering the restaurant.'),
(95, 'Eco Packaging Incentive', 'Customers receive incentives for reusable containers.'),
(96, 'Digital Menu Available', 'Menus can be accessed digitally via QR code.'),
(97, 'Multi Language Menu', 'Menus are available in multiple languages.'),
(98, 'Prayer Room Available', 'A prayer room is available for customers.'),
(99, 'Customer Feedback Program', 'Customer feedback is actively collected and reviewed.'),
(100, 'Health Inspection Certified', 'Restaurant complies with health inspection standards.');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `allergen`
--
ALTER TABLE `allergen`
  ADD PRIMARY KEY (`allergen_id`);

--
-- Indexes for table `dietary_type`
--
ALTER TABLE `dietary_type`
  ADD PRIMARY KEY (`dietary_id`);

--
-- Indexes for table `ingredient`
--
ALTER TABLE `ingredient`
  ADD PRIMARY KEY (`ingredient_id`);

--
-- Indexes for table `item_allergen`
--
ALTER TABLE `item_allergen`
  ADD PRIMARY KEY (`item_id`,`allergen_id`),
  ADD KEY `allergen_id` (`allergen_id`);

--
-- Indexes for table `item_dietary`
--
ALTER TABLE `item_dietary`
  ADD PRIMARY KEY (`item_id`,`dietary_id`),
  ADD KEY `dietary_id` (`dietary_id`);

--
-- Indexes for table `menu_ingredient`
--
ALTER TABLE `menu_ingredient`
  ADD PRIMARY KEY (`item_id`,`ingredient_id`),
  ADD KEY `ingredient_id` (`ingredient_id`);

--
-- Indexes for table `menu_item`
--
ALTER TABLE `menu_item`
  ADD PRIMARY KEY (`item_id`);

--
-- Indexes for table `restaurant_policy`
--
ALTER TABLE `restaurant_policy`
  ADD PRIMARY KEY (`policy_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `allergen`
--
ALTER TABLE `allergen`
  MODIFY `allergen_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=101;

--
-- AUTO_INCREMENT for table `dietary_type`
--
ALTER TABLE `dietary_type`
  MODIFY `dietary_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=101;

--
-- AUTO_INCREMENT for table `ingredient`
--
ALTER TABLE `ingredient`
  MODIFY `ingredient_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=101;

--
-- AUTO_INCREMENT for table `menu_item`
--
ALTER TABLE `menu_item`
  MODIFY `item_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=101;

--
-- AUTO_INCREMENT for table `restaurant_policy`
--
ALTER TABLE `restaurant_policy`
  MODIFY `policy_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=101;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `item_allergen`
--
ALTER TABLE `item_allergen`
  ADD CONSTRAINT `item_allergen_ibfk_1` FOREIGN KEY (`item_id`) REFERENCES `menu_item` (`item_id`),
  ADD CONSTRAINT `item_allergen_ibfk_2` FOREIGN KEY (`allergen_id`) REFERENCES `allergen` (`allergen_id`);

--
-- Constraints for table `item_dietary`
--
ALTER TABLE `item_dietary`
  ADD CONSTRAINT `item_dietary_ibfk_1` FOREIGN KEY (`item_id`) REFERENCES `menu_item` (`item_id`),
  ADD CONSTRAINT `item_dietary_ibfk_2` FOREIGN KEY (`dietary_id`) REFERENCES `dietary_type` (`dietary_id`);

--
-- Constraints for table `menu_ingredient`
--
ALTER TABLE `menu_ingredient`
  ADD CONSTRAINT `menu_ingredient_ibfk_1` FOREIGN KEY (`item_id`) REFERENCES `menu_item` (`item_id`),
  ADD CONSTRAINT `menu_ingredient_ibfk_2` FOREIGN KEY (`ingredient_id`) REFERENCES `ingredient` (`ingredient_id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
