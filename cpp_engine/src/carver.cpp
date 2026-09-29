#include "carver.h"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <algorithm>
#include <iomanip>
#include <sstream>

struct Signature {
    std::string type;
    std::vector<unsigned char> header;
    std::vector<unsigned char> footer;
    size_t max_size;
    std::string ext;
};

std::string format_size(size_t size) {
    std::stringstream ss;
    if (size > 1024 * 1024) {
        ss << std::fixed << std::setprecision(1) << (size / (1024.0 * 1024.0)) << " MB";
    } else {
        ss << std::fixed << std::setprecision(1) << (size / 1024.0) << " KB";
    }
    return ss.str();
}

std::vector<unsigned char> read_bytes(std::ifstream& f, size_t offset, size_t size) {
    std::vector<unsigned char> buf(size);
    f.seekg(offset, std::ios::beg);
    f.read(reinterpret_cast<char*>(buf.data()), size);
    buf.resize(f.gcount());
    return buf;
}

size_t find_sequence(const std::vector<unsigned char>& data, const std::vector<unsigned char>& seq, size_t start_pos = 0) {
    if (seq.empty() || start_pos >= data.size()) return std::string::npos;
    auto it = std::search(data.begin() + start_pos, data.end(), seq.begin(), seq.end());
    if (it != data.end()) {
        return std::distance(data.begin(), it);
    }
    return std::string::npos;
}

void emit_candidate(const std::string& type, size_t offset, size_t size, const std::string& output) {
    // Windows path escaping
    std::string escaped_output = output;
    size_t pos = 0;
    while ((pos = escaped_output.find("\\", pos)) != std::string::npos) {
        escaped_output.replace(pos, 1, "\\\\");
        pos += 2;
    }
    
    std::cout << "{\"type\":\"candidate\",\"file_type\":\"" << type 
              << "\",\"offset\":" << offset 
              << ",\"size\":" << size 
              << ",\"output\":\"" << escaped_output << "\"}\n";
    std::cout.flush();
}

void emit_progress(size_t processed, size_t total, int percentage) {
    std::cout << "{\"type\":\"progress\",\"processed\":" << processed 
              << ",\"total\":" << total 
              << ",\"progress\":" << percentage << "}\n";
    std::cout.flush();
}

void scan_image(CarveContext& context) {
    std::vector<Signature> signatures = {
        {"JPG", {0xFF, 0xD8, 0xFF}, {0xFF, 0xD9}, 5 * 1024 * 1024, ".jpg"},
        {"PNG", {0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A}, {0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82}, 5 * 1024 * 1024, ".png"},
        {"PDF", {'%', 'P', 'D', 'F', '-'}, {'%', '%', 'E', 'O', 'F'}, 10 * 1024 * 1024, ".pdf"},
        {"DOCX", {0x50, 0x4B, 0x03, 0x04}, {0x50, 0x4B, 0x05, 0x06}, 10 * 1024 * 1024, ".docx"}
    };

    std::ifstream file(context.input_path, std::ios::binary | std::ios::ate);
    if (!file) {
        std::cerr << "Error: Could not open " << context.input_path << std::endl;
        return;
    }

    size_t file_size = file.tellg();
    file.seekg(0, std::ios::beg);

    size_t bytes_processed = 0;
    size_t max_overlap = 8; 

    int last_progress = -1;

    while (bytes_processed < file_size) {
        size_t read_size = context.chunk_size + max_overlap;
        if (bytes_processed + read_size > file_size) {
            read_size = file_size - bytes_processed;
        }

        std::vector<unsigned char> chunk = read_bytes(file, bytes_processed, read_size);
        if (chunk.empty()) break;

        for (const auto& sig : signatures) {
            size_t start_idx = 0;
            while (true) {
                size_t idx = find_sequence(chunk, sig.header, start_idx);
                if (idx == std::string::npos) break;

                size_t absolute_offset = bytes_processed + idx;
                
                // Read potential file data
                std::vector<unsigned char> potential_data = read_bytes(file, absolute_offset, sig.max_size);
                
                size_t extracted_size = 0;
                size_t footer_idx = find_sequence(potential_data, sig.footer);
                
                if (footer_idx != std::string::npos) {
                    extracted_size = footer_idx + sig.footer.size();
                    if (sig.type == "DOCX") {
                        extracted_size += 18; // Complete EOCD
                    }
                } else {
                    extracted_size = std::min(potential_data.size(), (size_t)(100 * 1024)); // 100 KB default
                }
                
                // Save file
                context.files_found++;
                std::string filename = "recovered_" + std::string(3 - std::to_string(context.files_found).length(), '0') + std::to_string(context.files_found) + sig.ext;
                std::string out_path = context.output_dir + "/" + filename;
                
                std::ofstream out_f(out_path, std::ios::binary);
                if (out_f) {
                    out_f.write(reinterpret_cast<const char*>(potential_data.data()), extracted_size);
                    out_f.close();
                }

                emit_candidate(sig.type, absolute_offset, extracted_size, out_path);

                start_idx = idx + 1; // Find next
            }
        }

        bytes_processed += context.chunk_size;
        int progress = (int)((double)bytes_processed / file_size * 100);
        if (progress > 100) progress = 100;
        
        // Only emit if percentage changed to avoid spamming 
        if (progress != last_progress) {
            emit_progress(bytes_processed, file_size, progress);
            last_progress = progress;
        }
        
        file.seekg(bytes_processed, std::ios::beg); // Reset read pointer for next chunk
    }
    
    emit_progress(file_size, file_size, 100);
}
