// [LOCALIZATION-BANNER] Fork for the ROBOTICS;NOTES DaSH Simplified Chinese patch.
// Forked from CommitteeOfZero/LanguageBarrier (base commit cc982fd9),
// maintained at https://github.com/Syun1524/RND_Chinese
// See FORK-NOTES.md for the full change list. For upstream, use the CoZ repo.
#include "LanguageBarrier.h"
#include <dbghelp.h>
#include <malloc.h>
#include <string>
#include <iomanip>
#include "Config.h"
#include "SigExpr.h"

// Stolen from
// https://raw.githubusercontent.com/learn-more/findpattern-bench/master/patterns/atom0s_mrexodia.h

namespace {
using namespace std;

struct PatternByte {
  struct PatternNibble {
    unsigned char data;
    bool wildcard;
  } nibble[2];
};

static string FormatPattern(string patterntext) {
  string result;
  int len = patterntext.length();
  for (int i = 0; i < len; i++)
    if (patterntext[i] == '?' || isxdigit(patterntext[i]))
      result += toupper(patterntext[i]);
  return result;
}

static int HexChToInt(char ch) {
  if (ch >= '0' && ch <= '9')
    return ch - '0';
  else if (ch >= 'A' && ch <= 'F')
    return ch - 'A' + 10;
  else if (ch >= 'a' && ch <= 'f')
    return ch - 'a' + 10;
  return 0;
}

static bool TransformPattern(string patterntext, vector<PatternByte>& pattern) {
  pattern.clear();
  patterntext = FormatPattern(patterntext);
  int len = patterntext.length();
  if (!len) return false;

  if (len % 2)  // not a multiple of 2
  {
    patterntext += '?';
    len++;
  }

  PatternByte newByte;
  for (int i = 0, j = 0; i < len; i++) {
    if (patterntext[i] == '?')  // wildcard
    {
      newByte.nibble[j].wildcard = true;  // match anything
    } else                                // hex
    {
      newByte.nibble[j].wildcard = false;
      newByte.nibble[j].data = HexChToInt(patterntext[i]) & 0xF;
    }

    j++;
    if (j == 2)  // two nibbles = one byte
    {
      j = 0;
      pattern.push_back(newByte);
    }
  }
  return true;
}

static bool MatchByte(const unsigned char byte, const PatternByte& pbyte) {
  int matched = 0;

  unsigned char n1 = (byte >> 4) & 0xF;
  if (pbyte.nibble[0].wildcard)
    matched++;
  else if (pbyte.nibble[0].data == n1)
    matched++;

  unsigned char n2 = byte & 0xF;
  if (pbyte.nibble[1].wildcard)
    matched++;
  else if (pbyte.nibble[1].data == n2)
    matched++;

  return (matched == 2);
}

uintptr_t FindPattern(const unsigned char* dataStart,
                      const unsigned char* dataEnd, const char* pszPattern,
                      uintptr_t baseAddress, size_t offset, int occurrence) {
  // Build vectored pattern..
  vector<PatternByte> patterndata;
  if (!TransformPattern(pszPattern, patterndata)) return NULL;

  // The result count for multiple results..
  int resultCount = 0;
  const unsigned char* scanStart = dataStart;

  while (true) {
    // Search for the pattern..
    const unsigned char* ret = search(scanStart, dataEnd, patterndata.begin(),
                                      patterndata.end(), MatchByte);

    // Did we find a match..
    if (ret != dataEnd) {
      // If we hit the usage count, return the result..
      if (occurrence == 0 || resultCount == occurrence)
        return baseAddress + distance(dataStart, ret) + offset;

      // Increment the found count and scan again..
      resultCount++;
      scanStart = ++ret;
    } else
      break;
  }

  return NULL;
}
}  // namespace

namespace lb {
uintptr_t sigScanRaw(const char* category, const char* sigName,
                     bool isData = false) {
  std::stringstream logstr;
  logstr << "SigScan: looking for " << category << "/" << sigName << "... "
         << std::endl;

  json sig = config["gamedef"]["signatures"][category][sigName];

  // `pattern` is normally a single string, but may also be an array of strings.
  // The array form lists the SAME function as compiled by different game builds
  // (the executable's code generation changed between releases, so one byte
  // pattern cannot cover every version). They are tried in order and the first
  // match wins, which lets one gamedef serve several game versions.
  std::vector<std::string> patterns;
  if (sig["pattern"].is_array()) {
    for (auto& p : sig["pattern"]) patterns.push_back(p.get<std::string>());
  } else {
    patterns.push_back(sig["pattern"].get<std::string>());
  }
  size_t offset = sig["offset"].get<size_t>();
  int occurrence = sig["occurrence"].get<int>();

  HMODULE hModule = GetModuleHandleA(category);
  if (!hModule) hModule = GetModuleHandle(NULL);
  IMAGE_NT_HEADERS* pNtHdr = ImageNtHeader(hModule);
  IMAGE_SECTION_HEADER* pSectionHdr =
      (IMAGE_SECTION_HEADER*)((uint8_t*)&(pNtHdr->OptionalHeader) +
                              pNtHdr->FileHeader.SizeOfOptionalHeader);

  for (size_t pi = 0; pi < patterns.size(); pi++) {
    const char* pattern = patterns[pi].c_str();
    if (patterns.size() > 1) {
      logstr << (pi == 0 ? "[variant 1] " : "[variant 2] ") << patterns[pi];
    } else {
      logstr << patterns[pi];
    }
    logstr << std::endl;

    IMAGE_SECTION_HEADER* pSec = pSectionHdr;
    for (size_t i = 0; i < pNtHdr->FileHeader.NumberOfSections; i++) {
      if (isData == !!(pSec->Characteristics & IMAGE_SCN_MEM_EXECUTE)) {
        pSec++;
        continue;
      }

      uintptr_t baseAddress = (uintptr_t)hModule + pSec->VirtualAddress;
      uintptr_t retval = (uintptr_t)FindPattern(
          (unsigned char*)baseAddress,
          (unsigned char*)baseAddress + pSec->Misc.VirtualSize, pattern,
          baseAddress, offset, occurrence);

      if (retval != NULL) {
        logstr << " found at 0x" << std::hex << retval;
        if (lb::IsInitialised) {
          LanguageBarrierLog(logstr.str());
        }
        return retval;
      }
      pSec++;
    }
  }
  logstr << " not found!";
  if (lb::IsInitialised) {
    LanguageBarrierLog(logstr.str());
  }
  return NULL;
}

uintptr_t sigScan(const char* category, const char* sigName,
                  bool isData = false) {
  if (config["gamedef"]["signatures"][category].count(sigName) == 0)
    return NULL;
  uintptr_t raw = sigScanRaw(category, sigName, isData);
  json sig = config["gamedef"]["signatures"][category][sigName];
  if (sig.count("expr") == 0) return raw;

  try {
    return SigExpr(sig["expr"].get<std::string>(), raw).evaluate();
  } catch (std::runtime_error& e) {
    LanguageBarrierLog(e.what());
    return NULL;
  }
}
}  // namespace lb