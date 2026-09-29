#include <iostream>
#include <string>
#include <vector>
#include "carver.h"

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: secera_carver <input_image> <output_dir>" << std::endl;
        return 1;
    }

    CarveContext context;
    context.input_path = argv[1];
    context.output_dir = argv[2];

    scan_image(context);

    // Final JSON-L completion message
    std::cout << "{\"type\":\"complete\",\"files_found\":" << context.files_found << "}\n";
    std::cout.flush();

    return 0;
}
