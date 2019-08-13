#include "vcd_reader.h"
#include <vector>
#include <deque>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <cstdio>
#include <cstdlib>
#include <cassert>
#include <cstring>
#include <sys/time.h>

uint64_t timestamp(){
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return 1000000L * tv.tv_sec + tv.tv_usec;
}

vcd_reader_t::vcd_reader_t(int argc, char** argv) {
  std::vector<std::string> args(argv + 1, argv + argc);
  clock = 1000;
  window = 1;
  out = "toggles.csv";
  for (auto &arg: args) {
    if (arg.find("+vcd=") == 0) {
      vcds.push_back(std::string(arg.c_str() + 5));
    }
    if (arg.find("+out=") == 0) {
      out = arg.c_str() + 5;
    }
    if (arg.find("+window=") == 0) {
      window = atol(arg.c_str() + 8);
    }
    if (arg.find("+signals=") == 0) {
      read_signals(arg.c_str() + 9);
    }
  }
  cur_values = NULL;
  prev_values = NULL;
  total_cycle = 0;
  total_reset_cycle = 0;
}

vcd_reader_t::~vcd_reader_t() {
  delete [] cur_toggles;
  for (size_t i = 0 ; i < signals.size() ; i++) {
    delete[] cur_values[i];
    delete[] prev_values[i];
  }
  delete[] cur_values;
  delete[] prev_values;
}

void vcd_reader_t::read_signals(const char* filename) {
  std::ifstream file(filename);

  if (!file) {
    fprintf(stderr, "Connot open %s\n", filename);
    exit(EXIT_FAILURE);
  }

  std::string line;
  while (std::getline(file, line)) {
    char* token = strtok((char*)line.c_str(), ",");
    filter.insert(std::string(token));
  }
}

uint64_t vcd_reader_t::decode_symbol(const char* symbol) {
  size_t len = 0;
  uint64_t code = 0;
  while(*symbol) {
    code |= (*symbol++ << (8 * len++));
  }
  assert(len <= sizeof(uint64_t));
  return code;
}

uint16_t vcd_reader_t::hamming_dist(const char* x, const char* y) {
  uint16_t dist = 0;
  while (*x || *y) {
    dist += *x++ != *y++;
  }
  return dist;
}

void vcd_reader_t::decode_defs(char* token, bool first) {
  static bool is_prefix = true;
  static std::string prefix = "";
  static std::string path = "";
  static std::deque<std::string> paths;
  static size_t signal_idx = 0;
  static size_t total_width = 0;
  static bool is_bit_signal = false;

  #define next_token token = strtok(NULL, " ")

  if (strcmp(token,"$scope") == 0) {
    next_token;
    assert(strcmp(token, "module") == 0);
    next_token;
    paths.push_back(token);
    path = path + token + ".";
    if (is_prefix) prefix = path;
    next_token;
    assert(strcmp(token, "$end") == 0);
    is_prefix = true;
  } else if (strcmp(token, "$upscope") == 0) {
    paths.pop_back();
    path = "";
    for (auto &p: paths) {
      path += p + ".";
    }
  } else if (strcmp(token, "$var") == 0) {
    is_prefix = false;
    next_token;
    if (strcmp(token, "integer") == 0) return;
    assert(strcmp(token, "wire") == 0 ||
           strcmp(token, "reg") == 0);

    next_token;
    size_t width = atoi(token);
    total_width += width;

    next_token;
    uint64_t symbol = decode_symbol(token);

    next_token;
    // strip prefix
    std::string signal(path.c_str() + strlen(prefix.c_str()));
    signal += token;

    next_token;
    size_t idx = -1;
    if (strcmp(token, "$end") == 0) {
      assert(total_width = 1);
      is_bit_signal = false;
    } else {
      size_t len = strlen(token);
      assert(token[0] == '[' && token[len - 1] == ']');
      std::string range(token + 1, len - 2);
      if (width == 1) {
        idx = atoi(range.c_str());
        bit_symbols[symbol] = idx;
        is_bit_signal = true;
      } else {
        size_t pos = range.find(':');
        assert(pos != std::string::npos);
        size_t high = atoi(range.substr(0, pos).c_str());
        size_t low = atoi(range.substr(pos + 1).c_str());
        assert(low == 0 && high == (width - 1));
        is_bit_signal = false;
      }
      next_token;
      assert(strcmp(token, "$end") == 0);
    }
    
    #define in_signal(x) signal.find(x) != std::string::npos
    if (signal.find("clock") == 0) {
      clock_symbol = symbol;
      clock_value = 0;
      total_width = 0;
    } else if (signal.find("reset") == 0) {
      reset_symbol = symbol;
      reset_value = 0;
      total_width = 0;
    } else if (!filter.empty() && filter.find(signal) == filter.end()) {
      // skip
      total_width = 0;
    } else if (in_signal("clock") || in_signal("reset") || in_signal("_clk") ||
        in_signal("_rst") || in_signal("initvar") || in_signal("_RAND") ||
        in_signal("_GEN_") || (in_signal("_ext") && in_signal("_reg"))) { // FIXME: due to circuit mismatch
      // skip
      total_width = 0;
    } else {
      if (!first) {
        // VCS doesn't dump vars in-order...
        auto it = std::find(signals.begin(), signals.end(), signal);
        assert(it != signals.end());
        signal_idx = std::distance(signals.begin(), it);
      }
      if (symbols.find(symbol) == symbols.end()) {
        symbols[symbol] = signal_idx;
      }
      if (!is_bit_signal || idx == 0) {
        if (first) {
          signals.push_back(signal);
          widths.push_back(total_width);
          signal_idx++;
        } else {
          assert(signals[signal_idx] == signal);
          assert(widths[signal_idx] == total_width);
        }
        total_width = 0;
      }
    }

    #undef not_in_signal
  } else if (strcmp(token, "$enddefinitions") == 0) {
    assert(signals.size() == widths.size());
    if (first) {
      cur_toggles = new uint32_t[signals.size()];
      cur_values  = new char*[signals.size()];
      prev_values = new char*[signals.size()];
    }
    for (size_t i = 0 ; i < widths.size() ; i++) {
      size_t width = widths[i];
      if (first) {
        prev_values[i] = new char[width+1];
        cur_values[i]  = new char[width+1];
      }
      for (size_t k = 0 ; k < width ; k++) {
        prev_values[i][k] = '0';
      }
      prev_values[i][width] = 0;
      cur_values[i][width] = 0;
      cur_toggles[i] = 0;
      if (first) {
        indices.push_back(std::vector<size_t>());
        toggles.push_back(std::vector<uint32_t>());
        has_toggled.push_back(false);
      } else {
        has_toggled[i] = false;
      }
    }
    signal_idx = 0;
  } else {
  }
  #undef next_token  
}

void vcd_reader_t::decode_vals(char* token) {
  char* token2 = strtok(NULL, " ");
  uint64_t symbol;
  if (token2) {
    // bus
    symbol = decode_symbol(token2);
    if (clock_value == 1) {
      auto id = symbols.find(symbol);
      if (id != symbols.end()) {
        size_t i = id->second;
        assert(token[0] == 'b');
        assert(strlen(token+1) >= widths[i]);
        strncpy(cur_values[i], token+1, widths[i]);
        has_toggled[i] = true;
      }
    }
  } else {
    // bit
    symbol = decode_symbol(token + 1);
    if (symbol == clock_symbol) {
      clock_value = token[0] - '0';
      if (time > 0 && clock_value == 1) {
        cycle++;
        total_cycle++;
        assert((uint64_t)time == cycle * 1000); // FIXME: remove?
      }
    } else if (symbol == reset_symbol) {
      reset_value = token[0] - '0';
    } else if (clock_value == 1) {
      auto id = symbols.find(symbol);
      if (id != symbols.end()) {
        size_t i = id->second;
        auto off_id = bit_symbols.find(symbol);
        size_t off = off_id == bit_symbols.end() ? 0 : off_id->second;
        cur_values[i][off] = token[0];
        has_toggled[i] = true;
      }
    }
  }
}

void vcd_reader_t::update_toggles() {
  for (size_t i = 0 ; i < has_toggled.size() ; i++) {
    if (has_toggled[i]) {
      cur_toggles[i] += hamming_dist(prev_values[i], cur_values[i]);
      strcpy(prev_values[i], cur_values[i]);
      has_toggled[i] = false;
    }
  }

  size_t _cycles = total_cycle - total_reset_cycle;
  if (reset_value == 0 && _cycles > 0 && (_cycles % window == 0)) {
    size_t idx = _cycles / window - 1;
    for (size_t i = 0 ; i < widths.size() ; i++) {
      if (cur_toggles[i] > 0) {
        indices[i].push_back(idx);
        toggles[i].push_back(cur_toggles[i]);
        // toggles[i].push_back((float)cur_toggles[i] / (widths[i] * window));
        cur_toggles[i] = 0;
      }
    }
  }
}

void vcd_reader_t::read(std::string& vcd, bool first) {
  std::ifstream file(vcd.c_str());
  if (!file) {
    fprintf(stderr, "Connot open %s\n", vcd.c_str());
    exit(EXIT_FAILURE);
  }

  symbols.clear();
  bit_symbols.clear();

  std::string line;
  while (std::getline(file, line)) {
    if (line.empty()) continue;

    char* token = strtok((char*)line.c_str(), " ");

    switch(token[0]) {
      case '$':
        decode_defs(token, first);
        break;
      case '#':
        if (time > 0 && clock_value == 0) {
          assert((uint64_t)(time - 500) == cycle * 1000); // FIXME: remove?
          if (reset_value == 1) {
            reset_cycle++;
            total_reset_cycle++;
          }
        }
        if (cycle > 0 && clock_value == 1) {
          assert((uint64_t)time == cycle * 1000); // FIXME: remove?
          update_toggles();
        }
        time = atoi(token + 1);
        break;
      default:
        if (time >= 0 && token)
          decode_vals(token);
        break;
    }
  }
}

void vcd_reader_t::read() {
  uint64_t start_time = timestamp();
  bool first = true;
  for (auto& vcd: vcds) {
    time = -1;
    cycle = 0;
    reset_cycle = 0;
    symbols.clear();
    read(vcd, first);
    fprintf(stderr, "vcd: %s, cycles: %llu, total_cycles: %llu\n",
      vcd.c_str(), (unsigned long long)cycle, (unsigned long long)total_cycle);
    cycles.push_back(cycle);
    reset_cycles.push_back(reset_cycle);
    first = false;
  }

  // Leftovers
  size_t _cycles = total_cycle - total_reset_cycle;
  size_t tail = _cycles % window;
  if (tail > 0) {
    size_t idx = _cycles / window;
    for (size_t i = 0 ; i < widths.size() ; i++) {
      if (cur_toggles[i] > 0) {
        indices[i].push_back(idx);
        toggles[i].push_back(cur_toggles[i]);
        // toggles[i].push_back((float)cur_toggles[i] / (widths[i] * tail));
        cur_toggles[i] = 0;
      }
    }
  }
  uint64_t end_time = timestamp();

  fprintf(stderr, "time: %.2f secs\n", (double)(end_time - start_time) / 1000000.0);
}

void vcd_reader_t::dump_csv() {
  std::ofstream file(out);
  // Window
  file << window << std::endl;
  // Cycles
  auto cycle_it = cycles.begin();
  file << *cycle_it++;
  while (cycle_it != cycles.end()) {
    file << "," << *cycle_it++;
  }
  file << std::endl;
  // Reset Cycles
  auto reset_cycle_it = reset_cycles.begin();
  file << *reset_cycle_it++;
  while (reset_cycle_it != reset_cycles.end()) {
    file << "," << *reset_cycle_it++;
  }
  file << std::endl;
  // Signal names
  auto signal_it = signals.begin();
  file << *signal_it++;
  while (signal_it != signals.end()) {
    file << "," << *signal_it++;
  }
  file << std::endl;
  // Widths
  auto width_it = widths.begin();
  file << *width_it++;
  while (width_it != widths.end()) {
    file << "," << *width_it++;
  }
  file << std::endl;
  // Index pointers
  size_t ptr = 0;
  file << ptr;
  for (auto &is: indices) {
    ptr += is.size();
    file << "," << ptr;
  }
  file << std::endl;
  // Indices + Toggles
  assert(indices.size() == toggles.size());
  for (size_t i = 0 ; i < indices.size() ; i++) {
    auto& is = indices[i];
    auto& ts = toggles[i];
    assert(is.size() == ts.size());
    for (size_t j = 0 ; j < is.size() ; j++) {
      file << is[j] << "," << ts[j] << std::endl;
    }
  }
  file.close();
}

void vcd_reader_t::dump_bin() {
  std::ofstream file(out, std::ios::binary | std::ios::out);
  assert(sizeof(size_t) == 8);
  // Window
  file.write((const char*)&window, sizeof(size_t));
  // Cycles
  size_t cycles_size = cycles.size();
  file.write((const char*)&cycles_size, sizeof(size_t));
  for (auto cycle: cycles) {
    file.write((const char*)&cycle, sizeof(uint64_t));
  }
  // Reset Cycles
  size_t reset_cycles_size = reset_cycles.size();
  file.write((const char*)&reset_cycles_size, sizeof(size_t));
  for (auto reset_cycle: reset_cycles) {
    file.write((const char*)&reset_cycle, sizeof(uint64_t));
  }
  // Signal names
  size_t signals_size = signals.size();
  file.write((const char*)&signals_size, sizeof(size_t));
  for (auto& signal: signals) {
    size_t signal_len = signal.length();
    file.write((const char*)&signal_len, sizeof(size_t));
    file.write((const char*)signal.c_str(), signal_len * sizeof(char));
  }
  // Widths
  size_t widths_size = widths.size();
  file.write((const char*)&widths_size, sizeof(size_t));
  for (auto width: widths) {
    file.write((const char*)&width, sizeof(size_t));
  }
  // Index pointers
  size_t idxptr_size = indices.size() + 1;
  file.write((const char*)&idxptr_size, sizeof(size_t));
  size_t ptr = 0;
  file.write((const char*)&ptr, sizeof(size_t));
  for (auto &is: indices) {
    ptr += is.size();
    file.write((const char*)&ptr, sizeof(size_t));
  }
  // Indices + Toggles
  assert(indices.size() == toggles.size());
  for (size_t i = 0 ; i < indices.size() ; i++) {
    auto& is = indices[i];
    auto& ts = toggles[i];
    assert(is.size() == ts.size());
    for (size_t j = 0 ; j < is.size() ; j++) {
      size_t index = is[j];
      uint32_t toggle = ts[j];
      file.write((const char*)&index, sizeof(size_t));
      file.write((const char*)&toggle, sizeof(uint32_t));
    }
  }
  file.close();
}

void vcd_reader_t::dump() {
  std::string ext = out.substr(out.length() - 3);
  if (ext == "csv")
    dump_csv();
  else
    dump_bin();
}

int main(int argc, char** argv) {
  vcd_reader_t reader(argc, argv);
  reader.read();
  reader.dump();
  return EXIT_SUCCESS;
}
