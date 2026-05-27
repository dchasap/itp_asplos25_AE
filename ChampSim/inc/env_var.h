#ifndef _ENV_VAR_H
#define _ENV_VAR_H

#include <string>
#include <optional>
#include <cstdlib>
#include <algorithm>
#include <cctype>

namespace champsim {

template<typename T>
class EnvVar {
public:
  // Return optional value parsed from environment variable `name`.
  static std::optional<T> get(const char* name);
  // Return value or default
  static T get_or(const char* name, const T& def) {
    auto v = get(name);
    return v ? *v : def;
  }
};

// Specialization for std::string
template<>
inline std::optional<std::string> EnvVar<std::string>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  return std::string(v);
}

// Helper to lowercase a string
inline std::string to_lower_copy(const std::string &s) {
  std::string r = s;
  std::transform(r.begin(), r.end(), r.begin(), [](unsigned char c){ return std::tolower(c); });
  return r;
}

// Specialization for bool
template<>
inline std::optional<bool> EnvVar<bool>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  std::string s = to_lower_copy(std::string(v));
  if (s == "1" || s == "true" || s == "yes" || s == "on") return true;
  if (s == "0" || s == "false" || s == "no" || s == "off") return false;
  std::cerr << "Invalid value for environment variable " << name << ": '" << v << "'\n";
  std::exit(1);
}

// Specialization for unsigned long long
template<>
inline std::optional<unsigned long long> EnvVar<unsigned long long>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  try {
    unsigned long long val = std::stoull(std::string(v));
    return val;
  } catch (...) {
    std::cerr << "Invalid numeric value for environment variable " << name << ": '" << v << "'\n";
    std::exit(1);
  }
}

// Specialization for long long
template<>
inline std::optional<long long> EnvVar<long long>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  try {
    long long val = std::stoll(std::string(v));
    return val;
  } catch (...) {
    std::cerr << "Invalid numeric value for environment variable " << name << ": '" << v << "'\n";
    std::exit(1);
  }
}

// Specialization for double
template<>
inline std::optional<double> EnvVar<double>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  try {
    double val = std::stod(std::string(v));
    return val;
  } catch (...) {
    std::cerr << "Invalid numeric value for environment variable " << name << ": '" << v << "'\n";
    std::exit(1);
  }
}

// Fallback numeric specialization for unsigned int
template<>
inline std::optional<unsigned int> EnvVar<unsigned int>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  try {
    unsigned long long val = std::stoull(std::string(v));
    return static_cast<unsigned int>(val);
  } catch (...) {
    std::cerr << "Invalid numeric value for environment variable " << name << ": '" << v << "'\n";
    std::exit(1);
  }
}

// Specialization for int
template<>
inline std::optional<int> EnvVar<int>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  try {
    int val = std::stoi(std::string(v));
    return val;
  } catch (...) {
    std::cerr << "Invalid numeric value for environment variable " << name << ": '" << v << "'\n";
    std::exit(1);
  }
}

// Specialization for unsigned long
template<>
inline std::optional<unsigned long> EnvVar<unsigned long>::get(const char* name) {
  char* v = std::getenv(name);
  if (!v) return std::nullopt;
  try {
    unsigned long val = std::stoul(std::string(v));
    return val;
  } catch (...) {
    std::cerr << "Invalid numeric value for environment variable " << name << ": '" << v << "'\n";
    std::exit(1);
  }
}

} // namespace champsim

#endif // _ENV_VAR_H
