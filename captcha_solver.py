#!/usr/bin/env python3
"""
BSE CAPTCHA Solver
==================
Uses a CNN trained on segmented character dataset to solve CAPTCHAs.

Features:
- Trains on dataset/0-9/A-F character samples
- CNN model for robust character recognition
- Full pipeline: preprocess → segment → classify
- Can solve batch of CAPTCHAs or single images
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
from collections import defaultdict
import pickle
import argparse

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
CHAR_SET = "0123456789ABCDEF"
CHAR_TO_IDX = {c: i for i, c in enumerate(CHAR_SET)}
IDX_TO_CHAR = {i: c for i, c in enumerate(CHAR_SET)}

def get_script_dir():
    import sys
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

SCRIPT_DIR = get_script_dir()
DATASET_DIR = SCRIPT_DIR / "dataset"

def get_model_path():
    path = SCRIPT_DIR / "captcha_solver_model.pth"
    if not path.exists() and SCRIPT_DIR.name == "dist":
        parent_path = SCRIPT_DIR.parent / "captcha_solver_model.pth"
        if parent_path.exists():
            return parent_path
    return path

MODEL_PATH = get_model_path()
CHAR_W, CHAR_H = 28, 28
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ─────────────────────────────────────────────
#  CHARACTER DATASET
# ─────────────────────────────────────────────
class CharacterDataset(Dataset):
    def __init__(self, dataset_dir=DATASET_DIR):
        self.samples = []
        for char_dir in dataset_dir.iterdir():
            if not char_dir.is_dir():
                continue
            char = char_dir.name
            if char not in CHAR_SET:
                continue
            
            for img_path in char_dir.glob("*.png"):
                self.samples.append((img_path, char))
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        img_path, char = self.samples[idx]
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        
        if img is None:
            # Fallback to blank image (black background) if read fails
            img = np.zeros((CHAR_H, CHAR_W), dtype=np.uint8)
        else:
            # Invert white bg/black char to black bg/white char to match inference
            img = cv2.bitwise_not(img)
        
        # Normalize to [0, 1]
        img = img.astype(np.float32) / 255.0
        
        # Convert to tensor (1, H, W)
        img_tensor = torch.from_numpy(img).unsqueeze(0)
        
        label = CHAR_TO_IDX[char]
        return img_tensor, label


# ─────────────────────────────────────────────
#  CNN MODEL
# ─────────────────────────────────────────────
class CharacterCNN(nn.Module):
    def __init__(self, num_classes=16):
        super().__init__()
        
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # 28 → 14
            
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # 14 → 7
            
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),  # 7 → 3
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(128 * 3 * 3, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes),
        )
    
    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


# ─────────────────────────────────────────────
#  TRAINING
# ─────────────────────────────────────────────
def train_model(epochs=20, batch_size=64, lr=0.001):
    """Train character recognition model."""
    
    print(f"\n{'='*70}")
    print(f"  TRAINING CHARACTER RECOGNITION MODEL")
    print(f"{'='*70}\n")
    
    # Load dataset
    dataset = CharacterDataset()
    print(f"Loaded {len(dataset)} character samples")
    
    if len(dataset) == 0:
        print("ERROR: No character samples found in dataset directory!")
        return
    
    # Split train/val
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(
        dataset, [train_size, val_size]
    )
    
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    
    # Model
    model = CharacterCNN(num_classes=16).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=3
    )
    
    best_val_acc = 0
    
    for epoch in range(epochs):
        # Train
        model.train()
        train_loss = 0
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
            
            optimizer.zero_grad()
            outputs = model(imgs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # Validate
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for imgs, labels in val_loader:
                imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
                outputs = model(imgs)
                loss = criterion(outputs, labels)
                val_loss += loss.item()
                
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()
        
        val_loss /= len(val_loader)
        val_acc = val_correct / val_total
        
        print(f"Epoch {epoch+1:>3}/{epochs}  "
              f"Train Loss: {train_loss:.4f}  "
              f"Val Loss: {val_loss:.4f}  "
              f"Val Acc: {val_acc:.4f}")
        
        scheduler.step(val_loss)
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"           -> Saved best model (acc: {val_acc:.4f})")
    
    print(f"\n{'-'*70}")
    print(f"  Training complete! Model saved to: {MODEL_PATH}")
    print(f"  Best validation accuracy: {best_val_acc:.4f}")
    print(f"{'-'*70}\n")


# ─────────────────────────────────────────────
#  INFERENCE
# ─────────────────────────────────────────────
def preprocess_captcha(img_path):
    """
    Preprocess CAPTCHA image: use Red channel to exclude red scribbles.
    Returns binary threshold image.
    """
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"Cannot read image: {img_path}")
    
    # Crop 4-pixel border from all edges to remove frame noise
    img = img[4:-4, 4:-4]
    
    # 1. Use Red channel for thresholding.
    #    In the R channel: characters are dark (~0), background is bright (~255),
    #    and red scribbles are ALSO bright (~150-220). Otsu on R channel naturally
    #    separates dark characters from both background and red noise.
    r_channel = img[:, :, 2]   # BGR → channel 2 = Red
    _, thresh = cv2.threshold(r_channel, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 2. Morphological opening to remove small noise specks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    # 3. Connected component area filter
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] < 15:
            thresh[labels == i] = 0
            
    return thresh


def segment_captcha(thresh):
    """Segment captcha into 5 characters using improved vertical projection with valley splitting."""
    H, W = thresh.shape
    expected = 5
    
    # Vertical projection
    proj = np.sum(thresh, axis=0) // 255
    proj_smooth = np.convolve(proj, np.ones(3) / 3, mode='same').astype(int)
    
    # Find ink columns
    ink_cols = proj_smooth > 1
    
    ink_indices = np.where(ink_cols)[0]
    if len(ink_indices) < expected:
        # Fallback to split entire range if too few ink pixels found
        cw = W // expected
        filtered = [(i * cw, (i + 1) * cw - 1) for i in range(expected)]
    else:
        x_start, x_end = int(ink_indices[0]), int(ink_indices[-1])
        
        # Find segments separated by gaps (projection <= 1)
        segments = []
        in_char  = False
        seg_s    = 0
        for x in range(x_start, x_end + 1):
            if ink_cols[x] and not in_char:
                seg_s   = x
                in_char = True
            elif not ink_cols[x] and in_char:
                segments.append((seg_s, x - 1))
                in_char = False
        if in_char:
            segments.append((seg_s, x_end))
            
        # Merge very narrow gaps (< 3 pixels apart)
        merged = [segments[0]] if segments else []
        for seg in segments[1:]:
            if seg[0] - merged[-1][1] < 3:
                merged[-1] = (merged[-1][0], seg[1])
            else:
                merged.append(seg)
                
        # Filter out extremely narrow noise segments (< 3 pixels wide)
        filtered = [seg for seg in merged if (seg[1] - seg[0] + 1) >= 3]
        
        if not filtered:
            filtered = [(x_start, x_end)]
            
        # 1. If we have too many segments, merge the closest ones
        while len(filtered) > expected:
            min_gap = float('inf')
            merge_idx = -1
            for i in range(len(filtered) - 1):
                gap = filtered[i+1][0] - filtered[i][1]
                if gap < min_gap:
                    min_gap = gap
                    merge_idx = i
            if merge_idx == -1:
                break
            new_seg = (filtered[merge_idx][0], filtered[merge_idx+1][1])
            filtered = filtered[:merge_idx] + [new_seg] + filtered[merge_idx+2:]
            
        # 2. If we have too few segments, split the widest ones using valley splitting
        attempts = 0
        while len(filtered) < expected and attempts < 10:
            attempts += 1
            widths = [seg[1] - seg[0] + 1 for seg in filtered]
            widest_idx = np.argmax(widths)
            ws, we = filtered[widest_idx]
            
            # Search for lowest local minimum (valley) in the widest segment
            pad = min(4, (we - ws) // 3)
            search_start = ws + pad
            search_end = we - pad
            if search_start < search_end:
                valley_idx = search_start + np.argmin(proj_smooth[search_start : search_end + 1])
            else:
                valley_idx = (ws + we) // 2
                
            new_seg1 = (ws, valley_idx - 1)
            new_seg2 = (valley_idx, we)
            filtered = filtered[:widest_idx] + [new_seg1, new_seg2] + filtered[widest_idx+1:]
            
    chars = []
    for (xs, xe) in filtered:
        # Add same 2px padding as training (extract_chars in segment_captcha_dataset.py)
        pad = 2
        xs_p = max(0, xs - pad)
        xe_p = min(W - 1, xe + pad)
        crop = thresh[:, xs_p:xe_p + 1]
        
        # Trim vertical whitespace
        row_proj = crop.sum(axis=1)
        ink_rows = np.where(row_proj > 0)[0]
        if len(ink_rows) >= 2:
            crop = crop[ink_rows[0]: ink_rows[-1] + 1, :]
        
        # Resize to uniform size
        resized = cv2.resize(crop, (CHAR_W, CHAR_H), interpolation=cv2.INTER_AREA)
        chars.append(resized)
        
    return chars



def solve_captcha(img_path, model=None):
    """Solve a single CAPTCHA image."""
    
    if model is None:
        model = CharacterCNN(num_classes=16).to(DEVICE)
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. "
                f"Please train the model first with: python {__file__} --train"
            )
        model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    
    model.eval()
    
    # Preprocess
    try:
        thresh = preprocess_captcha(img_path)
    except Exception as e:
        return None, str(e)
    
    # Segment
    try:
        chars = segment_captcha(thresh)
        if chars is None or len(chars) != 5:
            return None, "Segmentation failed"
    except Exception as e:
        return None, f"Segmentation error: {str(e)}"
    
    # Classify
    result = ""
    with torch.no_grad():
        for char_img in chars:
            # Normalize
            char_img = char_img.astype(np.float32) / 255.0
            
            # To tensor (1, 1, H, W)
            char_tensor = torch.from_numpy(char_img).unsqueeze(0).unsqueeze(0)
            char_tensor = char_tensor.to(DEVICE)
            
            # Predict
            output = model(char_tensor)
            _, pred_idx = torch.max(output, 1)
            result += IDX_TO_CHAR[pred_idx.item()]
    
    return result, None


def solve_batch(image_dir, output_file=None):
    """Solve a batch of CAPTCHA images."""
    
    print(f"\n{'='*70}")
    print(f"  SOLVING BATCH CAPTCHAS")
    print(f"{'='*70}\n")
    
    image_dir = Path(image_dir)
    model = CharacterCNN(num_classes=16).to(DEVICE)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    
    images = sorted(image_dir.glob("*.png"))
    print(f"Found {len(images)} images to solve\n")
    
    results = {}
    solved_count = 0
    
    for img_path in images:
        result, error = solve_captcha(img_path, model)
        
        if error:
            print(f"  {img_path.name:>20}  ERROR: {error}")
        else:
            print(f"  {img_path.name:>20}  ->  {result}")
            results[img_path.name] = result
            solved_count += 1
    
    print(f"\n{'-'*70}")
    print(f"  Solved: {solved_count}/{len(images)}")
    
    if output_file:
        with open(output_file, "w") as f:
            for fname, pred in sorted(results.items()):
                f.write(f"{fname}\t{pred}\n")
        print(f"  Results saved to: {output_file}")
    
    print(f"{'-'*70}\n")
    
    return results


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BSE CAPTCHA Solver")
    parser.add_argument("--train", action="store_true", help="Train the model")
    parser.add_argument("--epochs", type=int, default=20, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--solve", type=str, help="Path to CAPTCHA image to solve")
    parser.add_argument("--batch", type=str, help="Directory with CAPTCHAs to solve")
    parser.add_argument("--output", type=str, help="Output file for batch results")
    args = parser.parse_args()
    
    if args.train:
        train_model(epochs=args.epochs, batch_size=args.batch_size)
    elif args.solve:
        result, error = solve_captcha(args.solve)
        if error:
            print(f"ERROR: {error}")
        else:
            print(f"\nCAPTCHA Solution: {result}")
    elif args.batch:
        solve_batch(args.batch, args.output)
    else:
        print("""
Usage:
  
  # Train model on dataset
  python captcha_solver.py --train
  
  # Solve single CAPTCHA
  python captcha_solver.py --solve path/to/captcha.png
  
  # Solve batch of CAPTCHAs
  python captcha_solver.py --batch captchas/ --output results.txt
        """)
