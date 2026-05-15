from PIL import Image

def remove_black_bg(input_path, output_path):
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()
    
    newData = []
    for item in datas:
        # Calculate brightness (average of RGB)
        brightness = sum(item[0:3]) / 3.0
        
        # If it's almost pure black, make it completely transparent
        if brightness < 15:
            newData.append((item[0], item[1], item[2], 0))
        else:
            # Map brightness to alpha for smooth glowing edges
            # Bright pixels stay opaque, dark pixels become semi-transparent
            alpha = int((brightness / 255.0) * 255)
            # Boost alpha slightly so the brain doesn't become too transparent
            alpha = min(255, int(alpha * 1.5))
            newData.append((item[0], item[1], item[2], alpha))
            
    img.putdata(newData)
    img.save(output_path, "PNG")

remove_black_bg("hero_ai_brain.png", "hero_ai_brain.png")
print("Done making image transparent.")
