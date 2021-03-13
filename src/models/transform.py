import torch
import torch.nn as nn
import torch.nn.functional as F

class Segment1d(nn.Module):
    """
    Segmentation. Input tensor is 3-D (audio-like), but output tensor is 4-D (image-like).
    """
    def __init__(self, chunk_size, hop_size):
        super().__init__()
        
        self.chunk_size, self.hop_size = chunk_size, hop_size

    def forward(self, input):
        """
        Args:
            input (batch_size, num_features, n_frames)
        Returns:
            output (batch_size, num_features, S, chunk_size): S is length of global output, where S = (n_frames-chunk_size)//hop_size + 1
        """
        chunk_size, hop_size = self.chunk_size, self.hop_size
        batch_size, num_features, n_frames = input.size()
        
        input = input.view(batch_size, num_features, n_frames, 1)
        x = F.unfold(input, kernel_size=(chunk_size,1), stride=(hop_size,1)) # -> (batch_size, num_features*chunk_size, S), where S = (n_frames-chunk_size)//hop_size+1
        x = x.view(batch_size, num_features, chunk_size, -1)
        output = x.permute(0,1,3,2).contiguous() # -> (batch_size, num_features, S, chunk_size)
        
        return output
    
    def extra_repr(self):
        s = "chunk_size={chunk_size}, hop_size={hop_size}".format(chunk_size=self.chunk_size, hop_size=self.hop_size)
        return s

class OverlapAdd1d(nn.Module):
    """
    Overlap-add operation. Input tensor is 4-D (image-like), but output tensor is 3-D (audio-like).
    """
    def __init__(self, chunk_size, hop_size):
        super().__init__()
        
        self.chunk_size, self.hop_size = chunk_size, hop_size
        
    def forward(self, input):
        """
        Args:
            input: (batch_size, num_features, S, chunk_size)
        Returns:
            output: (batch_size, num_features, n_frames)
        """
        chunk_size, hop_size = self.chunk_size, self.hop_size
        batch_size, num_features, S, chunk_size = input.size()
        n_frames = (S - 1) * hop_size + chunk_size
        
        x = input.permute(0,1,3,2).contiguous() # -> (batch_size, num_features, chunk_size, S)
        x = x.view(batch_size, num_features*chunk_size, S) # -> (batch_size, num_features*chunk_size, S)
        output = F.fold(x, kernel_size=(chunk_size,1), stride=(hop_size,1), output_size=(n_frames,1)) # -> (batch_size, num_features, n_frames, 1)
        output = output.squeeze(dim=3)
        
        return output
    
    def extra_repr(self):
        s = "chunk_size={chunk_size}, hop_size={hop_size}".format(chunk_size=self.chunk_size, hop_size=self.hop_size)
        return s

class BandSplit(nn.Module):
    def __init__(self, sections, dim=2):
        super().__init__()

        self.sections = sections
        self.dim = dim
    
    def forward(self, input):
        """
        Args:
            input (batch_size, in_channels, n_bins, n_frames)
            output: tuple of (batch_size, in_channels, sections[0], n_frames), ... (batch_size, in_channels, sections[-1], n_frames), where sum of sections is equal to n_bins
        """
        return torch.split(input, self.sections, dim=self.dim)
    
    def extra_repr(self):
        s = "1-{}, [".format(sum(self.sections))

        
        s += "1-{}".format(self.sections[0])
        start = self.sections[0] + 1

        for n_bins in self.sections[1:]:
            s += ", {}-{}".format(start, start + n_bins - 1)
            start += n_bins
        s += "]"

        return s

def _test_segment():
    batch_size, num_features, n_frames = 2, 3, 5
    K, P = 3, 2

    input = torch.randint(0, 10, (batch_size, num_features, n_frames), dtype=torch.float)
    
    segment = Segment1d(K, hop_size=P)
    output = segment(input)
    
    print(input.size(), output.size())
    print(input)
    print(output)

def _test_overlap_add():
    batch_size, num_features, n_frames = 2, 3, 5
    K, P = 3, 2
    S = (n_frames-K)//P + 1

    input = torch.randint(0, 10, (batch_size, num_features, S, K), dtype=torch.float)
    
    overlap_add = OverlapAdd1d(K, hop_size=P)
    output = overlap_add(input)
    
    print(input.size(), output.size())
    print(input)
    print(output)

def _test_band_split():
    sections = [10, 20]
    batch_size, num_features, n_bins, n_frames = 2, 3, sum(sections), 5

    input = torch.randint(0, 10, (batch_size, num_features, n_bins, n_frames), dtype=torch.float)
    
    band_split = BandSplit(sections=sections)
    low, high = band_split(input)
    print(input.size(), low.size(), high.size())

if __name__ == '__main__':
    print("="*10, "Segment", "="*10)
    _test_segment()
    print()
    
    print("="*10, "OverlapAdd", "="*10)
    _test_overlap_add()
    print()

    print("="*10, "BandSplit", "="*10)
    _test_band_split()
    print()