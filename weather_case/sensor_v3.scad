module box_with_beams(size, wall=4) {
  inner_size = size - [wall, wall, wall]*2;
  center = (size - inner_size)/2;
  size_helf = size/2;
  
  difference()
  {
    cube(size);
    translate(center)
    {
      // now 'extrude' each side
      // Y extrude
      translate([0, -size_helf.y, 0])
      cube(inner_size + [0, size.y, 0]);

      // X extrude
      translate([-size_helf.x, 0, 0])
      cube(inner_size + [size.x, 0, 0]);
    
      // Z extrude
      translate([0, 0, -size_helf.z])
      cube(inner_size + [0, 0, size.x]);
    }
  }
  
  // 'beams' 2.0
  // plane with 'cutouts'
  module beams_v2(beam_size) {
    module hole_v2() {
      color("pink")
      //translate([0, wall*2.5, wall*1])
      rotate([0, 00, 0])
      cylinder(h = 100, r = wall, $fn=4);
    }
    
    difference()
    {
      color("black")
      cube(beam_size);
      xi = ceil(((beam_size.x - wall*2.5)*2)/wall*3);
      xj = ceil(beam_size.y / wall)/2 + 1;
      echo(beam_size=beam_size, xi=xi, xj=xj);
     
  // 2nd row translate([0, wall*1, wall*2.5]) N mod 2 != 0
  // 1st row translate([0, wall*2.5, wall*1]) N mod 2 == 0
      translate(-[beam_size.z, beam_size.z])
      for (i = [0:xi]) {
        for (j = [0:2:xj]) {
          translate([wall + i*wall*3, wall*2.5 + j/2*wall*3,-1])
          hole_v2();
        }
        for (j = [-1:2:xj]) {
          translate([wall*2.5, wall*2.5 + j/2*wall*3, -1])
          hole_v2();
        }
      }
    }
}

translate([0, wall, wall + inner_size.z])
rotate([0, 90, 0])
beams_v2([inner_size.z, inner_size.y, wall]);


translate([inner_size.x + wall, wall, wall + inner_size.z])
rotate([0, 90, 0])
beams_v2([inner_size.z, inner_size.y, wall]);


translate([center.x + inner_size.x, 0, wall + inner_size.z])
rotate([0, 90, 90])
beams_v2([inner_size.z, inner_size.x, wall]);

translate([center.x + inner_size.x, inner_size.y + wall, wall + inner_size.z])
rotate([0, 90, 90])
beams_v2([inner_size.z, inner_size.x, wall]);

  // add 'beams'
  module beam() {
  rotate([45, 0, 0])
  cube([wall, wall, size.z]);
  }
  if (0)
  {
  translate([0, 8, 0.5]) {
  beam();
  translate([0, 6, 0])
  beam();
  }
  translate([0, 8, 0.5]) 
  mirror([0, 1, 0])
  {
  beam();
  translate([0, 6, 0])
  beam();
  }
  }
  
  // due to openscad footery thi has to be last
    // bounding box
  //color("gray", 0.3) cube(size);
}

box_with_beams([20, 30, 10], wall=2);