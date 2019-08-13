#ifndef VCD_READER_H
#define VCD_READER_H

#include <string>
#include <vector>
#include <unordered_set>
#include <unordered_map>

class vcd_reader_t {
public:
  vcd_reader_t(int argc, char** argv);
  ~vcd_reader_t();
  void read();
  void dump();
private:
  // arguments
  std::vector<std::string> vcds;
  std::string out;
  size_t clock;
  size_t window;
  int64_t time;
  uint64_t cycle;
  uint64_t total_cycle;
  uint64_t reset_cycle;
  uint64_t total_reset_cycle;
  std::vector<uint64_t> cycles;
  std::vector<uint64_t> reset_cycles;

  uint64_t clock_symbol;
  uint64_t reset_symbol;
  char clock_value;
  char reset_value;
  std::unordered_set<std::string> filter;
  std::unordered_map<uint64_t, size_t> symbols;
  std::unordered_map<uint64_t, size_t> bit_symbols;
  std::vector<std::string> signals;
  std::vector<size_t> widths;

  uint32_t* cur_toggles;
  char** cur_values;
  char** prev_values;
  std::vector<std::vector<size_t>> indices;
  std::vector<std::vector<uint32_t>> toggles;
  std::vector<bool> has_toggled;

  void read_signals(const char* filename);
  void read(std::string& filename, bool first);
  void decode_defs(char* token, bool first);
  void decode_vals(char* token);
  void update_toggles();

  inline uint64_t decode_symbol(const char* symbol);
  inline uint16_t hamming_dist(const char* x, const char* y);

  void dump_csv();
  void dump_bin();
};

#endif // VCD_READER_H
