#include <rex/platform.h>
#include <rex/platform/dynlib.h>

static_assert(REX_PLATFORM_LINUX || REX_PLATFORM_MAC, "This file is POSIX-only");

#include <dlfcn.h>

namespace rex::platform {

DynamicLibrary::~DynamicLibrary() {
  Close();
}

DynamicLibrary::DynamicLibrary(DynamicLibrary&& other) noexcept
    : handle_(other.handle_), last_error_(std::move(other.last_error_)) {
  other.handle_ = nullptr;
}

DynamicLibrary& DynamicLibrary::operator=(DynamicLibrary&& other) noexcept {
  if (this != &other) {
    Close();
    handle_ = other.handle_;
    last_error_ = std::move(other.last_error_);
    other.handle_ = nullptr;
  }
  return *this;
}

bool DynamicLibrary::Load(const std::filesystem::path& path, SymbolResolution mode) {
  Close();
  int flags = (mode == SymbolResolution::kImmediate) ? RTLD_NOW : RTLD_LAZY;
  handle_ = dlopen(path.c_str(), flags);
  if (handle_ == nullptr) {
    // Port Android (ForzaHorizon2Recomp-Android-RexGlue): o codegen registra
    // os módulos facade com shared_lib_name sem prefixo/sufixo
    // ("fh2_XMediaFacade_default" — ver module_registry.cpp gerado), mas o
    // empacotamento Android (jniLibs) só leva arquivos "lib<nome>.so" e o
    // bionic NÃO normaliza o nome no dlopen. Evidência (device real, 2ª
    // sessão): "Failed to load shared library for module
    // 'xmediafacade_default.xex'" sem nenhuma tentativa no nativeloader.
    // Retentativa com a forma canônica "lib<nome>.so" antes de desistir —
    // o bionic resolve no nativeLibraryDir do app (namespace do classloader
    // que carregou este próprio .so). Para nomes já canônicos (caminho
    // absoluto de driver, "libvulkan_freedreno.so") alt_path == path e o
    // comportamento é idêntico ao anterior.
    const std::string name = path.filename().string();
    std::string alt = name;
    if (!alt.empty() && alt.rfind("lib", 0) != 0) {
      alt = "lib" + alt;
    }
    if (alt.find(".so") == std::string::npos) {
      alt += ".so";
    }
    const std::filesystem::path alt_path = path.parent_path() / alt;
    if (alt_path != path) {
      handle_ = dlopen(alt_path.c_str(), flags);
    }
    // Preserva o erro da TENTATIVA CANÔNICA (a mais acionável: nome real do
    // arquivo empacotado; ex.: "cannot locate symbol" aponta o símbolo
    // faltante). Se não houve retry, erro da primeira tentativa.
    const char* err = dlerror();
    last_error_ = err ? std::string(err) : std::string();
  } else {
    last_error_.clear();
  }
  return handle_ != nullptr;
}

void DynamicLibrary::Adopt(void* handle) {
  Close();
  handle_ = handle;
  last_error_.clear();
}

void DynamicLibrary::Close() {
  if (handle_) {
    dlclose(handle_);
    handle_ = nullptr;
  }
}

void* DynamicLibrary::GetRawSymbol(const char* name) const {
  if (!handle_)
    return nullptr;
  return dlsym(handle_, name);
}

}  // namespace rex::platform
