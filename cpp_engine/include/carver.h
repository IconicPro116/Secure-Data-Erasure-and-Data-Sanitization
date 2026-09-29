#ifndef CARVER_H
#define CARVER_H

#include <string>

struct CarveContext {
    std::string input_path;
    std::string output_dir;
    size_t chunk_size = 1024 * 1024; // 1 MB
    int files_found = 0;
};

void scan_image(CarveContext& context);

#endif // CARVER_H
