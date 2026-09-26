// [LOCALIZATION-BANNER] Fork for the ROBOTICS;NOTES DaSH Simplified Chinese patch.
// Forked from CommitteeOfZero/LanguageBarrier (base commit cc982fd9),
// maintained at https://github.com/Syun1524/RND_Chinese
// See FORK-NOTES.md for the full change list. For upstream, use the CoZ repo.
#ifndef __LBJSON_H__
#define __LBJSON_H__

#include <nlohmann/json.hpp>
using json = nlohmann::json;

namespace lb {
// https://github.com/nlohmann/json/issues/252
json json_merge(const json &a, const json &b);
}  // namespace lb

#endif  // !__LBJSON_H__
