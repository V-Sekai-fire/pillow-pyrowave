// Python module pillow_pyrowave._pyrowave: decode(data) -> (width, height, rgb bytes).
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "decode.hpp"

namespace
{
PyObject* decode(PyObject*, PyObject* arg)
{
    Py_buffer view;
    if (PyObject_GetBuffer(arg, &view, PyBUF_SIMPLE) != 0)
        return nullptr;
    const auto* data = static_cast<const uint8_t*>(view.buf);
    const size_t size = size_t(view.len);
    pyrowave_pil::Header h;
    if (!pyrowave_pil::parseHeader(data, size, h))
    {
        PyBuffer_Release(&view);
        PyErr_SetString(PyExc_ValueError, "not a PyroWave frame: no start-of-frame sequence header");
        return nullptr;
    }
    const std::string reason = pyrowave_pil::unsupported(h);
    if (!reason.empty())
    {
        PyBuffer_Release(&view);
        PyErr_Format(PyExc_ValueError, "unsupported PyroWave frame: %s", reason.c_str());
        return nullptr;
    }
    pyrowave_pil::Planes planes;
    std::string error;
    std::vector<uint8_t> rgb;
    Py_BEGIN_ALLOW_THREADS
    error = pyrowave_pil::decodePlanes(data, size, h, planes);
    if (error.empty())
        rgb = pyrowave_pil::toRgb(planes, h.limited_range);
    Py_END_ALLOW_THREADS
    PyBuffer_Release(&view);
    if (!error.empty())
    {
        PyErr_Format(PyExc_OSError, "PyroWave decode failed: %s", error.c_str());
        return nullptr;
    }
    return Py_BuildValue("iiy#", h.width, h.height, reinterpret_cast<const char*>(rgb.data()),
                         Py_ssize_t(rgb.size()));
}

PyMethodDef methods[] = {
    {"decode", decode, METH_O, "decode(data) -> (width, height, rgb): one PyroWave frame to 8-bit RGB."},
    {nullptr, nullptr, 0, nullptr},
};

PyModuleDef module = {PyModuleDef_HEAD_INIT, "_pyrowave", "PyroWave decoder for pillow_pyrowave.", -1, methods};
} // namespace

PyMODINIT_FUNC PyInit__pyrowave()
{
    return PyModule_Create(&module);
}
