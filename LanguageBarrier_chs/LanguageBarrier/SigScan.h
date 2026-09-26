// [LOCALIZATION-BANNER] Fork for the ROBOTICS;NOTES DaSH Simplified Chinese patch.
// Forked from CommitteeOfZero/LanguageBarrier (base commit cc982fd9),
// maintained at https://github.com/Syun1524/RND_Chinese
// See FORK-NOTES.md for the full change list. For upstream, use the CoZ repo.
#ifndef __SIGSCAN_H__
#define __SIGSCAN_H__

#include <cstdint>

namespace lb {
uintptr_t sigScan(const char* category, const char* sigName,
                  bool isData = false);
}

#endif  // !__SIGSCAN_H__
