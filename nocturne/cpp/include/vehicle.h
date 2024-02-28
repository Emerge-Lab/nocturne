// Copyright (c) Facebook, Inc. and its affiliates.
// This source code is licensed under the MIT license found in the
// LICENSE file in the root directory of this source tree.

#pragma once

#include "geometry/vector_2d.h"
#include "object.h"

namespace nocturne {

class Vehicle : public Object {
 public:
  Vehicle() = default;

  Vehicle(int64_t id, float length, float width,
          const geometry::Vector2D& position, float heading, float speed,
          const geometry::Vector2D& target_position, float target_heading,
          float target_speed, bool is_av, bool can_block_sight = true,
          bool can_be_collided = true, bool check_collision = true)
      : Object(id, length, width, position, heading, speed, target_position,
               target_heading, target_speed, can_block_sight, can_be_collided,
               check_collision),
        is_av_(is_av) {
    Object::InitColor(sf::Color::Blue);
  }

  Vehicle(int64_t id, float length, float width, float max_speed,
          const geometry::Vector2D& position, float heading, float speed,
          const geometry::Vector2D& target_position, float target_heading,
          float target_speed, bool is_av, bool can_block_sight = true,
          bool can_be_collided = true, bool check_collision = true)
      : Object(id, length, width, max_speed, position, heading, speed,
               target_position, target_heading, target_speed, can_block_sight,
               can_be_collided, check_collision),
        is_av_(is_av) {
    Object::InitColor(sf::Color::Blue);
  }
  void colorAsSrc(const std::optional<sf::Color>& color = std::nullopt) {
    Object::InitColor(color);
  }

  ObjectType Type() const override { return ObjectType::kVehicle; }

  bool is_av() const { return is_av_; }

 protected:
  bool is_av_;
};

}  // namespace nocturne
