import warnings

import torch
import torch.nn as nn
import torch.nn.functional as F

EPS = 1e-12

class ConcatenatedReLU(nn.Module):
    def __init__(self, dim=1):
        super().__init__()

        warnings.warn("Use modules.activation.ConcatenatedReLU instead.", DeprecationWarning)

        self.dim = dim

    def forward(self, input):
        positive, negative = F.relu(input), F.relu(-input)
        output = torch.cat([positive, negative], dim=self.dim)

        return output

"""
    For complex input
"""
class ModReLU1d(nn.Module):
    def __init__(self, num_features):
        super().__init__()

        warnings.warn("Use modules.activation.ModReLU1d instead.", DeprecationWarning)

        self.num_features = num_features
        self.bias = nn.Parameter(torch.Tensor((num_features,)), requires_grad=True)

        self._reset_parameters()

    def _reset_parameters(self):
        self.bias.data.zero_()

    def forward(self, input):
        """
        Args:
            input <torch.Tensor>: Tensor with shape of
                (batch_size, num_features, T) if complex
                (batch_size, num_features, T, 2) otherwise
        Returns:
            output <torch.Tensor>: Tensor with shape of
                (batch_size, num_features, T) if complex
                (batch_size, num_features, T, 2) otherwise
        """
        is_complex = torch.is_complex(input)

        if not is_complex:
            input = torch.view_as_complex(input)

        magnitude = torch.abs(input)
        angle = torch.angle(input)
        magnitude = F.relu(magnitude + self.bias.unsqueeze(dim=-1))
        output = magnitude * torch.exp(1j * angle)

        if not is_complex:
            output = torch.view_as_real(output)

        return output

class ModReLU2d(nn.Module):
    def __init__(self, num_features):
        super().__init__()

        warnings.warn("Use modules.activation.ModReLU2d instead.", DeprecationWarning)

        self.num_features = num_features
        self.bias = nn.Parameter(torch.Tensor((num_features,)), requires_grad=True)

        self._reset_parameters()

    def _reset_parameters(self):
        self.bias.data.zero_()

    def forward(self, input):
        """
        Args:
            input <torch.Tensor>: Tensor with shape of
                (batch_size, num_features, height, width) if complex
                (batch_size, num_features, height, width, 2) otherwise
        Returns:
            output <torch.Tensor>: Tensor with shape of
                (batch_size, num_features, height, width) if complex
                (batch_size, num_features, height, width, 2) otherwise
        """
        is_complex = torch.is_complex(input)

        if not is_complex:
            input = torch.view_as_complex(input)

        magnitude = torch.abs(input)
        angle = torch.angle(input)
        magnitude = F.relu(magnitude + self.bias.unsqueeze(dim=-1).unsqueeze(dim=-1))
        output = magnitude * torch.exp(1j * angle)

        if not is_complex:
            output = torch.view_as_real(output)

        return output

class ComplexReLU(nn.Module):
    def __init__(self):
        super().__init__()

        warnings.warn("Use modules.activation.ComplexReLU instead.", DeprecationWarning)

    def forward(self, input):
        """
        Args:
            input <torch.Tensor>: (*)
        Returns:
            output <torch.Tensor>: (*)
        """
        is_complex = torch.is_complex(input)

        if not is_complex:
            input = torch.view_as_complex(input)

        real, imag = input.real, input.imag
        real, imag = F.relu(real), F.relu(imag)

        output = torch.complex(real, imag)

        if not is_complex:
            output = torch.view_as_real(output)

        return output

class ZReLU(nn.Module):
    def __init__(self):
        super().__init__()

        warnings.warn("Use modules.activation.ZReLU instead.", DeprecationWarning)

    def forward(self, input):
        """
        Args:
            input <torch.Tensor>: Complex tensor is acceptable. Shape: (*)
        Returns:
            output <torch.Tensor>: Real or complex tensor. Shape: (*)
        """
        is_complex = torch.is_complex(input)

        if not is_complex:
            input = torch.view_as_complex(input)

        real, imag = input.real, input.imag

        condition = torch.logical_and(real > 0, imag > 0)
        real = torch.where(condition, real, torch.zeros_like(real))
        imag = torch.where(condition, imag, torch.zeros_like(imag))

        output = torch.complex(real, imag)

        if not is_complex:
            output = torch.view_as_real(output)

        return output
