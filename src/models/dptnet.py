import torch
import torch.nn as nn
import torch.nn.functional as F

from utils.utils_tasnet import choose_bases, choose_layer_norm
from models.gtu import GTU1d
from models.dprnn_tasnet import Segment1d, OverlapAdd1d
from models.dptransformer import DualPathTransformer

EPS=1e-12

class DPTNet(nn.Module):
    """
    Dual-path transformer based network
    """
    def __init__(
        self,
        n_bases, kernel_size, stride=None,
        enc_bases=None, dec_bases=None,
        sep_bottleneck_channels=64, sep_hidden_channels=256,
        sep_chunk_size=100, sep_hop_size=None, sep_num_blocks=6,
        sep_num_heads=4, sep_norm=True, sep_nonlinear='relu', sep_dropout=0,
        mask_nonlinear='relu',
        causal=False,
        n_sources=2,
        eps=EPS,
        **kwargs
    ):
        super().__init__()
        
        if stride is None:
            stride = kernel_size//2
        
        if sep_hop_size is None:
            sep_hop_size = sep_chunk_size//2
        
        assert kernel_size%stride == 0, "kernel_size is expected divisible by stride"
        assert n_bases%sep_num_heads == 0, "n_bases must be divisible by sep_num_heads"
        
        # Encoder-decoder
        self.n_bases = n_bases
        self.kernel_size, self.stride = kernel_size, stride
        self.enc_bases, self.dec_bases = enc_bases, dec_bases
        
        if enc_bases == 'trainable' and not dec_bases == 'pinv':    
            self.enc_nonlinear = kwargs['enc_nonlinear']
        else:
            self.enc_nonlinear = None
        
        if enc_bases in ['Fourier', 'trainableFourier'] or dec_bases in ['Fourier', 'trainableFourier']:
            self.window_fn = kwargs['window_fn']
        else:
            self.window_fn = None
        
        # Separator configuration
        self.sep_bottleneck_channels, self.sep_hidden_channels = sep_bottleneck_channels, sep_hidden_channels
        self.sep_chunk_size, self.sep_hop_size = sep_chunk_size, sep_hop_size
        self.sep_num_blocks = sep_num_blocks
        self.sep_num_heads = sep_num_heads
        self.sep_norm = sep_norm
        self.sep_nonlinear = sep_nonlinear
        self.sep_dropout = sep_dropout

        self.causal = causal
        self.mask_nonlinear = mask_nonlinear
        
        self.n_sources = n_sources
        self.eps = eps
        
        # Network configuration
        encoder, decoder = choose_bases(n_bases, kernel_size=kernel_size, stride=stride, enc_bases=enc_bases, dec_bases=dec_bases, **kwargs)
        
        self.encoder = encoder
        self.separator = Separator(
            n_bases, bottleneck_channels=sep_bottleneck_channels, hidden_channels=sep_hidden_channels,
            chunk_size=sep_chunk_size, hop_size=sep_hop_size, num_blocks=sep_num_blocks,
            num_heads=sep_num_heads, norm=sep_norm, nonlinear=sep_nonlinear, dropout=sep_dropout,
            mask_nonlinear=mask_nonlinear,
            causal=causal,
            n_sources=n_sources,
            eps=eps
        )
        self.decoder = decoder
        
        self.num_parameters = self._get_num_parameters()
        
    def forward(self, input):
        output, latent = self.extract_latent(input)
        
        return output
        
    def extract_latent(self, input):
        """
        Args:
            input (batch_size, 1, T)
        Returns:
            output (batch_size, n_sources, T)
            latent (batch_size, n_sources, n_bases, T'), where T' = (T-K)//S+1
        """
        n_sources = self.n_sources
        n_bases = self.n_bases
        kernel_size, stride = self.kernel_size, self.stride
        
        batch_size, C_in, T = input.size()
        
        assert C_in == 1, "input.size() is expected (?,1,?), but given {}".format(input.size())
        
        padding = (stride - (T-kernel_size)%stride)%stride
        padding_left = padding//2
        padding_right = padding - padding_left

        input = F.pad(input, (padding_left, padding_right))
        w = self.encoder(input)
        mask = self.separator(w)
        w = w.unsqueeze(dim=1)
        w_hat = w * mask
        latent = w_hat
        w_hat = w_hat.view(batch_size*n_sources, n_bases, -1)
        x_hat = self.decoder(w_hat)
        x_hat = x_hat.view(batch_size, n_sources, -1)
        output = F.pad(x_hat, (-padding_left, -padding_right))
        
        return output, latent
    
    def get_package(self):
        package = {
            'n_bases': self.n_bases,
            'kernel_size': self.kernel_size,
            'stride': self.stride,
            'enc_bases': self.enc_bases,
            'dec_bases': self.dec_bases,
            'enc_nonlinear': self.enc_nonlinear,
            'window_fn': self.window_fn,
            'sep_hidden_channels': self.sep_hidden_channels,
            'sep_bottleneck_channels': self.sep_bottleneck_channels,
            'sep_chunk_size': self.sep_chunk_size,
            'sep_hop_size': self.sep_hop_size,
            'sep_num_blocks': self.sep_num_blocks,
            'sep_num_heads': self.sep_num_heads,
            'sep_norm': self.sep_norm,
            'sep_nonlinear': self.sep_nonlinear,
            'sep_dropout': self.sep_dropout,
            'mask_nonlinear': self.mask_nonlinear,
            'causal': self.causal,
            'n_sources': self.n_sources,
            'eps': self.eps
        }
    
        return package
    
    @classmethod
    def build_model(cls, model_path):
        package = torch.load(model_path, map_location=lambda storage, loc: storage)
        
        n_bases = package['n_bases']
        kernel_size, stride = package['kernel_size'], package['stride']
        enc_bases, dec_bases = package['enc_bases'], package['dec_bases']
        enc_nonlinear = package['enc_nonlinear']
        window_fn = package['window_fn']
        
        sep_hidden_channels, sep_bottleneck_channels = package['sep_hidden_channels'], package['sep_bottleneck_channels']
        sep_chunk_size, sep_hop_size = package['sep_chunk_size'], package['sep_hop_size']
        sep_num_blocks = package['sep_num_blocks']
        sep_num_heads = package['sep_num_heads']
        sep_norm, sep_nonlinear, sep_dropout = package['sep_norm'], package['sep_nonlinear'], package['sep_dropout']
        
        sep_nonlinear, sep_norm = package['sep_nonlinear'], package['sep_norm']
        mask_nonlinear = package['mask_nonlinear']

        causal = package['causal']
        n_sources = package['n_sources']
        
        eps = package['eps']

        model = cls(
            n_bases, kernel_size, stride=stride,
            enc_bases=enc_bases, dec_bases=dec_bases, enc_nonlinear=enc_nonlinear, window_fn=window_fn,
            sep_bottleneck_channels=sep_bottleneck_channels, sep_hidden_channels=sep_hidden_channels,
            sep_chunk_size=sep_chunk_size, sep_hop_size=sep_hop_size, sep_num_blocks=sep_num_blocks,
            sep_num_heads=sep_num_heads,
            sep_norm=sep_norm, sep_nonlinear=sep_nonlinear, sep_dropout=sep_dropout,
            mask_nonlinear=mask_nonlinear,
            causal=causal,
            n_sources=n_sources,
            eps=eps
        )
        
        return model
    
    def _get_num_parameters(self):
        num_parameters = 0
        
        for p in self.parameters():
            if p.requires_grad:
                num_parameters += p.numel()
                
        return num_parameters

class Separator(nn.Module):
    def __init__(
        self,
        num_features, bottleneck_channels=32, hidden_channels=128,
        chunk_size=100, hop_size=None, num_blocks=6,
        num_heads=4,
        norm=True, nonlinear='relu', dropout=0,
        mask_nonlinear='relu',
        causal=True,
        n_sources=2,
        eps=EPS
    ):
        super().__init__()

        if hop_size is None:
            hop_size = chunk_size//2
        
        self.num_features, self.n_sources = num_features, n_sources
        self.chunk_size, self.hop_size = chunk_size, hop_size
        
        self.bottleneck_conv1d = nn.Conv1d(num_features, bottleneck_channels, kernel_size=1, stride=1)
        self.segment1d = Segment1d(chunk_size, hop_size)
        self.norm2d = choose_layer_norm(bottleneck_channels, causal=causal, eps=eps)

        self.dptransformer = DualPathTransformer(
            bottleneck_channels, hidden_channels,
            num_blocks=num_blocks, num_heads=num_heads,
            norm=norm, nonlinear=nonlinear, dropout=dropout,
            causal=causal, eps=eps
        )
        self.overlap_add1d = OverlapAdd1d(chunk_size, hop_size)
        self.prelu = nn.PReLU()
        self.map = nn.Conv1d(bottleneck_channels, n_sources*num_features, kernel_size=1, stride=1)
        self.gtu = GTU1d(num_features, num_features)
        
        if mask_nonlinear == 'relu':
            self.mask_nonlinear = nn.ReLU()
        elif mask_nonlinear == 'sigmoid':
            self.mask_nonlinear = nn.Sigmoid()
        elif mask_nonlinear == 'softmax':
            self.mask_nonlinear = nn.Softmax(dim=1)
        else:
            raise ValueError("Cannot support {}".format(mask_nonlinear))
            
    def forward(self, input):
        """
        Args:
            input (batch_size, num_features, n_frames)
        Returns:
            output (batch_size, n_sources, num_features, n_frames)
        """
        num_features, n_sources = self.num_features, self.n_sources
        chunk_size, hop_size = self.chunk_size, self.hop_size
        batch_size, num_features, n_frames = input.size()
        
        padding = (hop_size-(n_frames-chunk_size)%hop_size)%hop_size
        padding_left = padding//2
        padding_right = padding - padding_left
        
        x = self.bottleneck_conv1d(input)
        x = F.pad(x, (padding_left, padding_right))
        x = self.segment1d(x) # -> (batch_size, C, S, chunk_size)
        x = self.norm2d(x)
        x = self.dptransformer(x)
        x = self.overlap_add1d(x)
        x = F.pad(x, (-padding_left, -padding_right))
        x = self.prelu(x) # -> (batch_size, C, n_frames)
        x = self.map(x) # -> (batch_size, n_sources*C, n_frames)
        x = x.view(batch_size*n_sources, num_features, n_frames) # -> (batch_size*n_sources, num_features, n_frames)
        x = self.gtu(x) # -> (batch_size*n_sources, num_features, n_frames)
        x = self.mask_nonlinear(x) # -> (batch_size*n_sources, num_features, n_frames)
        output = x.view(batch_size, n_sources, num_features, n_frames)
        
        return output

def _test_separator():
    batch_size = 2
    T_bin = 64
    n_sources = 3

    num_features = 10
    d = 12 # must be divisible by num_heads
    d_ff = 15
    chunk_size = 10 # local chunk length
    num_blocks = 3
    num_heads = 4 # multihead attention in transformer

    input = torch.randn((batch_size, num_features, T_bin), dtype=torch.float)
    
    causal = False

    separator = Separator(
        num_features, hidden_channels=d_ff, bottleneck_channels=d,
        chunk_size=chunk_size, num_blocks=num_blocks, num_heads=num_heads,
        causal=causal,
        n_sources=n_sources
    )
    print(separator)

    output = separator(input)
    print(input.size(), output.size())

def _test_dptnet():
    batch_size = 2
    T = 64

    # Encoder decoder
    N, L = 12, 8
    enc_bases, dec_bases = 'trainable', 'trainable'
    enc_nonlinear = 'relu'
    
    # Separator
    d = 32 # must be divisible by num_heads
    d_ff = 4 * d # depth of feed-forward network
    K = 10 # local chunk length
    B, h = 3, 4 # number of dual path transformer processing block, and multihead attention in transformer
    mask_nonlinear = 'relu'
    n_sources = 2

    input = torch.randn((batch_size, 1, T), dtype=torch.float)
    
    causal = False

    model = DPTNet(
        N, L, enc_bases=enc_bases, dec_bases=dec_bases, enc_nonlinear=enc_nonlinear,
        sep_bottleneck_channels=d, sep_hidden_channels=d_ff,
        sep_chunk_size=K, sep_num_blocks=B, sep_num_heads=h,
        mask_nonlinear=mask_nonlinear,
        causal=causal,
        n_sources=n_sources
    )
    print(model)

    output = model(input)
    print("# Parameters: {}".format(model.num_parameters))
    print(input.size(), output.size())

def _test_dptnet_paper():
    batch_size = 2
    T = 64

    # Encoder decoder
    N, L = 64, 2
    enc_bases, dec_bases = 'trainable', 'trainable'
    enc_nonlinear = 'relu'
    
    # Separator
    d = 32
    d_ff = 4 * d # depth of feed-forward network
    K = 10 # local chunk length
    B, h = 6, 4 # number of dual path transformer processing block, and multihead attention in transformer
    
    mask_nonlinear = 'relu'
    n_sources = 2

    input = torch.randn((batch_size, 1, T), dtype=torch.float)
    
    causal = False

    model = DPTNet(
        N, L, enc_bases=enc_bases, dec_bases=dec_bases, enc_nonlinear=enc_nonlinear,
        sep_bottleneck_channels=N, sep_hidden_channels=d_ff,
        sep_chunk_size=K, sep_num_blocks=B, sep_num_heads=h,
        mask_nonlinear=mask_nonlinear,
        causal=causal,
        n_sources=n_sources
    )
    print(model)

    output = model(input)
    print("# Parameters: {}".format(model.num_parameters))
    print(input.size(), output.size())

if __name__ == '__main__':
    print('='*10, "Separator based on dual path transformer network", '='*10)
    _test_separator()
    print()

    print('='*10, "Dual path transformer network", '='*10)
    _test_dptnet()
    print()

    print('='*10, "Dual path transformer network (same configuration in the paper)", '='*10)
    _test_dptnet_paper()
    print()