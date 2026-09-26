// [LOCALIZATION-BANNER] Fork for the ROBOTICS;NOTES DaSH Simplified Chinese patch.
// Forked from CommitteeOfZero/LanguageBarrier (base commit cc982fd9),
// maintained at https://github.com/Syun1524/RND_Chinese
// See FORK-NOTES.md for the full change list. For upstream, use the CoZ repo.
#include "LanguageBarrier.h"
#include "lbjson.h"

namespace lb {
json json_merge(const json &a, const json &b) {
  if (!a.is_object() || !b.is_object()) return b;

  json result = a;

  for (json::const_iterator it = b.begin(); it != b.end(); ++it) {
    const auto &key = it.key();
    if (a.count(key) != 1) {
      result[key] = b[key];
    } else {
      result[key] = json_merge(a[key], b[key]);
    }
  }

  return result;
}
}  // namespace lb